"""
Competency ratings and next scenario recommendation.

Every critical action is treated as a match between the learner's rating in
that action's competency and the action's difficulty rating:

    expected = 1 / (1 + 10 ** ((difficulty - learner) / 400))
    result   = 1.0 on time, 0.5 late, 0.0 missed
    learner += K * (result - expected)
    action  -= K_ACTION * (result - expected)

Actions that most learners miss drift upward in difficulty on their own.
"""
import pandas as pd

from .catalog import COMPETENCIES, SCENARIOS

START = 1200
K = 28
K_ACTION = 8
TARGET_P = 0.62          # sweet spot: likely to succeed, still a stretch
RESULT = {"on_time": 1.0, "late": 0.5, "missed": 0.0}


def expected(learner, difficulty):
    return 1.0 / (1.0 + 10 ** ((difficulty - learner) / 400.0))


def initial_difficulty():
    diff = {}
    for sc_id, sc in SCENARIOS.items():
        for a in sc["actions"]:
            # tighter targets mean harder actions
            diff[(sc_id, a["id"])] = sc["difficulty"] - 120 + 4 * (60 - min(a["target_sec"], 120)) / 2
    return diff


def run_ratings(sessions, actions):
    """Replay all training sessions in time order. Returns (history, current, difficulty)."""
    diff = initial_difficulty()
    rating = {}
    hist = []
    s = sessions[sessions["mode"] == "training"].sort_values("started_at")
    by_session = {k: g for k, g in actions.groupby("session_id")}
    for _, row in s.iterrows():
        acts = by_session.get(row.session_id)
        if acts is None:
            continue
        for _, a in acts.sort_values("order").iterrows():
            key = (row.learner_id, a.competency)
            r = rating.get(key, START)
            d = diff[(row.scenario_id, a.action_id)]
            e = expected(r, d)
            res = RESULT[a.status]
            rating[key] = r + K * (res - e)
            diff[(row.scenario_id, a.action_id)] = d - K_ACTION * (res - e)
        for comp in COMPETENCIES:
            hist.append({"learner_id": row.learner_id, "session_id": row.session_id,
                         "started_at": row.started_at, "competency": comp,
                         "rating": round(rating.get((row.learner_id, comp), START), 1)})
    history = pd.DataFrame(hist)
    current = (history.sort_values("started_at").groupby(["learner_id", "competency"])
               .tail(1)[["learner_id", "competency", "rating"]].reset_index(drop=True))
    difficulty = pd.DataFrame([{"scenario_id": k[0], "action_id": k[1], "difficulty": round(v, 1)}
                               for k, v in diff.items()])
    return history, current, difficulty


def recommend(learner_id, current, difficulty, done_scenarios, top_n=3):
    """Rank scenarios by how well they stretch the learner's weakest competencies."""
    mine = current[current.learner_id == learner_id].set_index("competency").rating
    if mine.empty:
        mine = pd.Series({c: START for c in COMPETENCIES})
    weakest = mine.sort_values().index.tolist()
    weight = {c: 1.0 / (1 + i) for i, c in enumerate(weakest)}  # weakest counts most
    rows = []
    for sc_id, sc in SCENARIOS.items():
        fit, focus, ps = 0.0, {}, []
        for a in sc["actions"]:
            d = difficulty[(difficulty.scenario_id == sc_id) &
                           (difficulty.action_id == a["id"])].difficulty.iloc[0]
            p = expected(mine.get(a["comp"], START), d)
            ps.append((p, a["weight"]))
            closeness = 1 - min(abs(p - TARGET_P) / TARGET_P, 1)
            fit += weight[a["comp"]] * closeness * a["weight"]
            focus[a["comp"]] = focus.get(a["comp"], 0) + a["weight"]
        repeats = done_scenarios.count(sc_id)
        fit *= 0.85 ** repeats
        main_comp = max(focus, key=lambda c: focus[c] * weight[c])
        rows.append({"scenario_id": sc_id, "name": sc["name"], "fit": round(fit, 1),
                     "targets": main_comp, "times_done": repeats,
                     "p": sum(p * w for p, w in ps) / sum(w for _, w in ps)})
    ranked = sorted(rows, key=lambda r: -r["fit"])[:top_n]
    for r in ranked:
        comp = r["targets"]
        n = sum(1 for a in SCENARIOS[r["scenario_id"]]["actions"] if a["comp"] == comp)
        r["why"] = (f"{COMPETENCIES[comp]} is rated {mine.get(comp, START):.0f}, "
                    f"{'your lowest' if comp == weakest[0] else 'one of your lower areas'}, and this scenario "
                    f"tests it in {n} of its 6 actions. Expected success across the scenario is about "
                    f"{r['p'] * 100:.0f}%. "
                    + (f"You have run it {r['times_done']} time{'s' if r['times_done'] > 1 else ''}."
                       if r["times_done"] else "You have not run it yet."))
    return ranked, weakest
