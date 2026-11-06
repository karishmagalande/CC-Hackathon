"""
Debrief notes for one session.

facts()     builds a list of timestamped observations straight from the data.
template()  turns them into Plus / Delta / Next notes. Always works offline.
narrative() optionally asks a language model (any OpenAI compatible endpoint,
            including a local Ollama server) to write a short debrief from the
            same facts. Falls back to template() on any error.

Configure in .env:
  LENS_LLM_BASE_URL=http://localhost:11434/v1     (Ollama)  or  https://api.openai.com/v1
  LENS_LLM_MODEL=llama3.1:8b
  LENS_LLM_API_KEY=ollama
"""
import os

import requests

from .catalog import COMPETENCIES, SCENARIOS


def mmss(t):
    if t is None:
        return "--:--"
    t = max(0, float(t))
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def facts(session, actions, cues, taps, dwell):
    sc = SCENARIOS[session["scenario_id"]]
    onset = session["onset_t"]
    plus, delta = [], []
    for _, a in actions.sort_values("order").iterrows():
        if a.status == "on_time":
            gd = a.ghost_delta
            tail = "" if gd is None or gd != gd else (
                f", {abs(gd):.0f}s {'ahead of' if gd < 0 else 'behind'} the expert run")
            plus.append((a.t_abs, f"{a.label} at {mmss(a.t_abs)}, {a.t_rel:.0f}s after the change{tail}."))
        elif a.status == "late":
            delta.append((a.t_abs, f"{a.label} at {mmss(a.t_abs)}, {a.t_rel:.0f}s after the change "
                                    f"(target {a.target_sec}s)."))
        else:
            delta.append((onset + a.target_sec, f"{a.label} was not done (target {a.target_sec}s "
                                                f"after the change)."))
    for t0, t1 in cues:
        delta.append((t0, f"From {mmss(t0)} to {mmss(t1)} the patient was unstable while attention "
                          f"was away from both patient and monitor."))
    if session["gaze_monitor"] > 0.40:
        delta.append((onset, f"{session['gaze_monitor'] * 100:.0f}% of looking time after the change went "
                             f"to the monitor. The patient got {session['gaze_patient'] * 100:.0f}%."))
    elif session["gaze_patient"] >= 0.40:
        plus.append((onset, f"Kept eyes on the patient: {session['gaze_patient'] * 100:.0f}% of looking time "
                            f"after the change."))
    if len(taps) >= 4:
        obj = taps.object.value_counts().idxmax()
        delta.append((float(taps.t.min()), f"{len(taps)} touches with no effect on equipment, "
                                           f"mostly the {obj.replace('_', ' ')}."))
    if session["instability_sec"] <= 30:
        plus.append((onset, f"Patient spent only {session['instability_sec']}s outside safe ranges."))
    return {
        "scenario": sc["name"], "score": session["score"],
        "plus": [p[1] for p in sorted(plus, key=lambda x: x[0])],
        "delta": [d[1] for d in sorted(delta, key=lambda x: x[0])],
    }


def template(f, weakest_comp=None):
    nxt = []
    if f["delta"]:
        nxt.append("Rerun this scenario and aim to close the first item under Delta.")
    if weakest_comp:
        nxt.append(f"Focus area from your ratings: {COMPETENCIES[weakest_comp]}.")
    return {"plus": f["plus"] or ["Completed the scenario."],
            "delta": f["delta"] or ["Nothing flagged. Try a harder scenario."],
            "next": nxt, "source": "rules"}


def llm_configured():
    return bool(os.getenv("LENS_LLM_BASE_URL") and os.getenv("LENS_LLM_MODEL"))


def narrative(f, learner_name, timeout=25):
    if not llm_configured():
        return None
    prompt = (
        "You are a pediatric simulation educator writing a short debrief for a learner. "
        "Use only the observations below. Do not add clinical facts that are not listed. "
        "Keep timestamps exactly as written. Write three short paragraphs: what went well, "
        "what to work on, and one concrete goal for the next run. Under 140 words. Plain language.\n\n"
        f"Learner: {learner_name}\nScenario: {f['scenario']}\nScore: {f['score']}\n"
        "Went well:\n- " + "\n- ".join(f["plus"] or ["none"]) +
        "\nTo work on:\n- " + "\n- ".join(f["delta"] or ["none"])
    )
    try:
        r = requests.post(
            os.getenv("LENS_LLM_BASE_URL").rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('LENS_LLM_API_KEY', 'none')}"},
            json={"model": os.getenv("LENS_LLM_MODEL"), "temperature": 0.3,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # network, auth, model missing: never break the demo
        return f"__error__ {e}"
