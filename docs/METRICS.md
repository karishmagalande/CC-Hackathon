# Metric definitions

All times relative to **onset**, the moment the patient engine enters `deteriorating`, unless stated.

| Metric | Definition |
|---|---|
| Action status | `on_time` if the action's rule first matches within `target_sec` of onset, `late` if it matches after that, `missed` if never |
| Score | Sum of points / sum of weights × 100. On time = full weight, late = half, missed = 0 |
| Cue to action | Seconds from onset to the first completed critical action |
| Time to rescue | Seconds from onset to the scenario's rescue action (the one that reverses deterioration) |
| Unstable time | Seconds after onset with any vital outside the scenario's safe range (`danger` in catalog.py) |
| Gaze shares | Share of fixation time after onset on patient, monitor, equipment, environment |
| Missed cue | A run of 6 s or more where the patient is unstable and no fixation is on the patient or monitor |
| Ghost delta | Learner `t_rel` minus expert reference `t_rel`, per completed action |
| Pre-touch dwell | Seconds of gaze on a device in the 10 s before its first effective use |
| No-effect touches | Count of `tap` records: touches on a control that changed nothing |

## Ratings

Every critical action is a match between the learner's rating in its competency and the action's difficulty.

```
expected = 1 / (1 + 10 ^ ((difficulty - learner) / 400))
result   = 1 on time, 0.5 late, 0 missed
learner += 28 × (result - expected)
action  -=  8 × (result - expected)
```

Learners start at 1200. Action difficulty starts from the scenario's base difficulty, adjusted for how tight the target is, and then drifts with real results.

## Recommendation

For each scenario, the expected success of every action is computed from the learner's current ratings. Actions near 62% expected success score highest, and the learner's weakest competencies are weighted most. Scenarios already run lose a little weight each time, to encourage variety. The top result names the competency it targets, the expected success rate, and how many times it has been run.

## Value Ledger

```
mannequin cost = sessions × (facilitator h × rate + tech h × rate + room/supplies)
VR cost        = sessions × (VR facilitator min / 60 × rate + headset/licence)
hours freed    = sessions × (facilitator h + tech h - VR facilitator min / 60)
```

All inputs are editable on the page.
