# Data dictionary

## Raw headset log (`data/raw/sessions/<session_id>.jsonl`)

One JSON object per line. Times `t` are seconds from session start.

| k | Fields | Meaning |
|---|---|---|
| `meta` | session_id, learner_id, scenario_id, attempt, started_at, headset, build, mode | Session header. `mode` is `training` or `reference` (expert ghost run) |
| `evt` | t, v (verb), o (object), x (target) | An interaction, e.g. `attach bvm patient_face`, `use phone speed_dial_help` |
| `tap` | t, o, x (control), fx | A touch on an equipment control that had no effect (`fx` = 0) |
| `fix` | t0, t1, o | A gaze fixation on an object |
| `pose` | t, x, y | Head position in metres, top-down, 1 Hz |
| `vit` | t, hr, spo2, rr, sbp | Patient engine vitals, 1 Hz |
| `state` | t, s | Patient engine state change: `deteriorating`, `responding` |
| `end` | t, reason | Session end |

Verbs: `touch`, `grab`, `use`, `attach`, `set`, `administer`, `manipulate`, `look_confirm`.

Objects: `patient`, `monitor`, `phone`, `bvm`, `o2_flow`, `suction`, `iv_pump`, `vent`, `med_cart`, `penlight`, `clock`, `door`, `sink`, `elsewhere`.

## Other raw files

| File | Columns |
|---|---|
| `roster.csv` | learner_id, display_name, role, unit, cohort, experience_years |
| `surveys.csv` | learner_id, competency, pre_confidence, post_confidence (1 to 5) |
| `_profiles.csv` | learner_id, profile. Ground truth for testing only, never read by the app |

## Processed tables (`data/processed/`)

| Table | Grain | Key columns |
|---|---|---|
| `sessions` | session | meta fields, onset_t, duration, score, on_time, late, missed, cue_to_action, time_to_rescue, instability_sec, min_spo2, gaze_patient/monitor/equipment/environment, missed_cues, missed_cue_sec, no_effect_taps, ghost_delta_total |
| `actions` | session × critical action | action_id, label, competency, order, weight, target_sec, t_abs, t_rel, expert_rel, ghost_delta, status, points |
| `events` | interaction | t, verb, object, target |
| `taps` | no-effect touch | t, object, control |
| `fixations` | gaze fixation | t0, t1, object |
| `poses` | second | t, x, y |
| `vitals` | second | t, hr, spo2, rr, sbp |
| `states` | state change | t, state |
| `device_dwell` | session × device | object, pre_touch_dwell |
| `rating_history` | session × competency | learner_id, started_at, competency, rating |
| `ratings` | learner × competency | rating (latest) |
| `action_difficulty` | scenario × action | difficulty (after replay) |
| `roster`, `surveys` | copied from raw | |
| `workflow_steps` | session × workflow step | session_id, step, t, lane, what (merged step labels, separated by `;`) |
| `role_standard` | role × step | role, step, lane, what, sessions (number of sessions used to find it) |

### Workflow columns added to `sessions`

| Column | Meaning |
|---|---|
| `cds_on` | the session had COMET available (simulation setting) |
| `workflow_role` | Provider, RN or RT, from the roster |
| `workflow_steps` | number of lane steps after merging |
| `lane_switches` | steps − 1 |
| `first_lane`, `first_info_lane` | first lane, and first lane that is not communication |
| `epic_before_assessment` | Epic interactions before the first patient assessment |
| `time_to_bedside` | seconds to the first patient assessment step |
| `time_to_first_communication` | seconds to the first communication step after the start |
| `workflow_match` | 0 to 100, closeness to the role's standard path (COMET excluded) |
| `workflow_missing` | standard steps the session skipped |
| `cds_viewed` | the learner looked at COMET |
| `cds_view_after_change` | seconds from the patient change to the first COMET view |
| `cds_to_next_action` | seconds from the COMET view to the next critical action |
| `lane_share_<lane>` | share of steps in each lane: epic, assessment, vitals, comet, communication |

### Lanes

| Lane | Logged as |
|---|---|
| `epic` | any interaction with object `epic` |
| `assessment` | anything on `patient` or `penlight`, and any `inspect` |
| `vitals` | `check` on `monitor` |
| `comet` | any interaction with object `comet` |
| `communication` | `communicate` or `use` on `team` or `phone` |

## Competency codes

| Code | Competency |
|---|---|
| REC | Recognition |
| COM | Communication |
| AIR | Airway & Breathing |
| CIR | Circulation & Meds |
| EQP | Equipment Fluency |
