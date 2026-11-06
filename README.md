# DISCOVER Lens

The data layer beside the headset.

DISCOVER is Cincinnati Children's VR digital twin for pediatric emergency training. The people who decide whether to adopt it (education directors, nurse leaders, administrators, industry partners) rarely put on a headset. DISCOVER Lens takes the telemetry a session already produces (every touch, every glance, every change in the simulated patient) and turns it into views for the learner, the educator and the partner.

Built for the Cincinnati Children's Digital Health Hackathon 2026. Everything runs on a laptop with synthetic sample data. No VR engine integration is needed.

---

## What makes it different

| Idea | What it shows |
|---|---|
| **Ghost Run** | Every critical action lined up against an expert reference run of the same scenario, as a two-lane timeline with per-action time deltas. Can also compare against the learner's own previous attempt. |
| **Cue to Action** | Patient vitals, the learner's gaze (the attention ribbon) and every action on one clock. Highlights **missed cues**: stretches where the patient was unstable and nobody was looking at the patient or the monitor. |
| **Room Replay** | A top-down room rebuilt from head position and gaze, with a gaze ray to whatever the learner was looking at. Play or scrub. |
| **Readiness Profile** | Competency ratings (Elo style) that update after every action, a trend, and a next-scenario recommendation that states its reason and expected success rate. |
| **Value Ledger** | Staff hours and cost compared with mannequin simulation, using assumptions the viewer can edit, plus a paragraph ready to paste into a proposal. |
| **Friction Lens** | For device partners: which equipment and which controls cost clinicians time in a crisis, measured from gaze dwell before use and touches that did nothing. Exportable. |
| **Workflow Map** | Each session as a swim lane path across five information sources: Epic, patient assessment, vital sign monitor, COMET / in-room view, and communication. The learner's path is drawn against their role's standard path, with sticky notes for each step and the COMET view marked as the CDS touchpoint. |
| **Role Workflows** | All sessions of one role overlaid to find the standard workflow for Provider, RN and RT. Shows where learners leave the standard (the CDS opportunity areas), how much each role relies on each information source, and what changes when COMET is used. |
| **Rules, not hard code** | Raw headset interactions become clinical actions through editable rules (`lens/catalog.py`). Point the pipeline at real DISCOVER exports and every view updates. |

---

## Quick start

You need **Python 3.10 or newer** (3.11 or 3.12 recommended) and Git.

### Mac / Linux

```bash
cd discover-lens
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/main.py
```

### Windows (PowerShell)

```powershell
cd discover-lens
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app/main.py
```

If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt with `.venv\Scripts\activate.bat`.

The browser opens at http://localhost:8501. On the first run the app generates the sample telemetry and builds the tables (about 10 seconds). Shortcut scripts do all of the above: `./run.sh` on Mac/Linux, `run.bat` on Windows.

### Rebuild the data yourself

```bash
python generator/make_raw.py --seed 7    # writes data/raw/ (175+ JSONL session logs)
python pipeline/build.py                 # writes data/processed/ (14 tables)
python tests/smoke_test.py               # checks the data tells the expected story
```

You can also regenerate with a new seed from the **Data & Pipeline** page.

---

## Optional: narrative debrief from a language model

The rule-based debrief (Plus / Delta / Next with timestamps) always works offline. To also get a short paragraph version, copy `.env.example` to `.env` and point it at any OpenAI-compatible endpoint.

**Local and offline with Ollama (recommended for the demo):**

```bash
# install from https://ollama.com, then
ollama pull llama3.1:8b
```

```
LENS_LLM_BASE_URL=http://localhost:11434/v1
LENS_LLM_MODEL=llama3.1:8b
LENS_LLM_API_KEY=ollama
```

**Hosted (OpenAI or similar):** set the base URL to `https://api.openai.com/v1`, a model name and your key. The prompt only passes the observations already shown on screen, and the model is told not to add clinical facts. If the call fails, the page says so and the rule-based debrief stays on screen.

---

## Project layout

```
discover-lens/
├── app/
│   ├── main.py              entry point and navigation
│   └── views/
│       ├── overview.py      landing page
│       ├── replay.py        Ghost Run, Cue to Action, Room Replay, Debrief
│       ├── report_card.py   Readiness Profile, recommendations, printable report
│       ├── cohort.py        learning curves, action reliability, who needs support
│       ├── value.py         Value Ledger with editable assumptions
│       ├── friction.py      Friction Lens for device partners
│       └── data_room.py     raw logs, rules, tables, regenerate
├── lens/
│   ├── catalog.py           room, competencies, scenarios, action rules  (edit me)
│   ├── metrics.py           scoring, missed cues, gaze shares, dwell
│   ├── ratings.py           Elo competency ratings and recommender
│   ├── debrief.py           rule-based and optional model-written debrief
│   ├── data.py              cached loading, first-run build
│   └── ui.py                colours, CSS, chart template
├── generator/make_raw.py    synthetic headset telemetry
├── pipeline/build.py        raw JSONL → tidy tables + metrics
├── tests/smoke_test.py
├── data/raw/                generated logs (committed so the demo works offline)
├── data/processed/          generated tables
├── docs/                    data dictionary, metric definitions, pitch script
├── requirements.txt  .env.example  run.sh  run.bat
```

---

## How the data works

1. **Raw logs** (`data/raw/sessions/*.jsonl`): one file per session, one JSON record per line, mixing event, touch, gaze fixation, head pose, vitals and state records the way a headset stream would arrive. See `docs/DATA_DICTIONARY.md`.
2. **Rules** turn interactions into clinical actions. For example "start bag-mask ventilation" is the first `attach` of `bvm` to `patient_face` after the patient starts to change.
3. **Metrics** score each action as on time, late or missed against its target, then compute cue-to-action, time to rescue, unstable seconds, gaze shares, missed cues and equipment dwell. See `docs/METRICS.md`.
4. **Ratings** replay every session in order. Each critical action is a match between the learner's competency rating and the action's difficulty.
5. **Views** read only the processed tables.

The simulated patient responds to the learner. Vitals worsen from the moment of deterioration and recover only after the scenario's rescue action. So a faster rescue really does produce less unstable time, and the outcome numbers come out of the simulation rather than being typed in.

### The sample cohort

36 learners (RN, residents, RT, NP) in two cohorts, 5 scenarios, about 175 sessions, plus one expert reference run per scenario. Learners follow hidden behaviour profiles so the views have real patterns to find: steady, monitor-fixated, solo operator (calls for help late), fast improver, and equipment-hesitant. `data/raw/_profiles.csv` holds the ground truth for checking. The app never reads it.

**Demo learner:** Maya O. (RN) runs Infant Respiratory Decompensation three times and climbs from about 50 to 72 to 92. Her sessions are pinned, so the story is the same on every machine.

---

## Workflow lanes and the CDS question

This follows the hackathon team's VR observation synthesis.

1. **Lanes.** Every logged interaction is placed in one lane (`event_lane` in `lens/catalog.py`). Consecutive steps in the same lane merge into one step, so a path reads like the team's swim lane maps.
2. **Standard path per role.** For each role, the standard is the real session path with the smallest total edit distance to every other session of that role (the medoid). It is always a path someone actually took. COMET views are left out of the standard so it describes the workflow without the CDS tool.
3. **Workflow match.** `100 × (1 − edit distance / longer path length)`, comparing the learner's path with their role's standard. 100 means the same sequence.
4. **Where learners leave the standard.** Each standard step a session skips (found by longest common subsequence) is counted. The most skipped steps are the opportunity areas for a CDS prompt.
5. **CDS placement and effect.** A COMET view after the patient changes is the CDS touchpoint. Sessions with and without it are compared on score, time to rescue, unstable time and workflow match. The page also shows when COMET was viewed and what the learner did next.

What the sample data shows (simulated, built to match the team's hypothesis):

| Role | What the team expected | What the data shows |
|---|---|---|
| Provider | Big picture first, gather information before entering the room | Most Epic views before reaching the patient (about 1.6 vs 0.8 for RN and 0 for RT), and the latest to the bedside |
| RN | In the room, relies on vitals, trends and assessment | Highest share of steps on the vital sign monitor (about a quarter) |
| RT | On the go, respiratory focus, checks equipment and the patient | Mostly assessment and communication, no Epic before the bedside |

Sessions that viewed COMET reached the rescue action about 14 seconds faster (median). **This is simulated data built around the hypothesis. It shows the method, not a finding.** With real DISCOVER logs the same pipeline produces the real answer.

Lane colours, role summaries and the hypothesised paths are all in `lens/catalog.py` (`LANES`, `ROLE_SUMMARY`, `ROLE_WORKFLOWS`).

## Plugging in real DISCOVER data

1. Export sessions in whatever format DISCOVER logs.
2. Change `parse_log()` in `pipeline/build.py` to map their field names onto the six record kinds.
3. Replace the scenarios, targets and rules in `lens/catalog.py` with the clinical team's definitions.
4. Run `python pipeline/build.py`. Nothing in `app/` changes.

---

## Notes

- All data is synthetic. No patient or learner information is used.
- Clinical target times in `catalog.py` are placeholders for the prototype and need to be set by the DISCOVER clinical team.
- Value Ledger figures depend entirely on the editable assumptions and show how the measure works, not a result.

## Troubleshooting

| Problem | Fix |
|---|---|
| `streamlit: command not found` | Activate the virtual environment first, or run `python -m streamlit run app/main.py` |
| Page shows old data after editing code | Press `R` in the browser, or use the menu: Clear cache |
| Port already in use | `streamlit run app/main.py --server.port 8502` |
| Fonts look plain | The IBM Plex fonts load from Google Fonts. Offline, the app falls back to system fonts, which is fine |
| Changes in `lens/` not picked up | Stop the server (Ctrl+C) and start it again |
