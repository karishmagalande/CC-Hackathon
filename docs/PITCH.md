# Pitch and demo script (3 minutes)

## One line

DISCOVER already records every step a clinician takes in the headset. DISCOVER Lens turns those steps into the three role workflows the team drew by hand, shows where people leave them, and measures what COMET changes.

## Time plan

| Time | Where | What you say |
|---|---|---|
| 0:00 – 0:15 | Overview | The problem in one breath |
| 0:15 – 0:55 | Session Replay, Maya O. (RN), attempt 1 | Ghost Run, then scroll to 04 Workflow map |
| 0:55 – 1:50 | Role Workflows | The heart of the demo: three workflows, opportunity areas, COMET |
| 1:50 – 2:20 | Report Card, then Cohort | Same idea for one learner and for the program |
| 2:20 – 2:45 | Data & Pipeline | Real logs drop in, lanes are a config |
| 2:45 – 3:00 | Close | What we need from the DISCOVER team |

## Script

**0:00 · Overview (15 s)**
"Your team watched VR sessions and drew swim lanes by hand to find how each role works. We built the tool that does that automatically, for every session, from the data the headset already logs."

**0:15 · Session Replay → Maya O., RN, attempt 1 (40 s)**
- Ghost Run (top): "Grey is the expert, colour is Maya. She missed the call for help and the airway reposition."
- Scroll to **04 Workflow map**: "This is your swim lane slide, generated. Five lanes: Epic, patient assessment, vital sign monitor, COMET, communication. Yellow notes are what she did. The faint numbered line is the standard RN workflow. She matches it 75 percent, and she never looked at COMET."

**0:55 · Role Workflows (55 s)**
- Section 01: "Every session overlaid, per role, just like your slide three. The thick line is the standard: the real path closest to everyone else's."
- Read the three blue lines under the role headers: "Providers check Epic before the patient, about one and a half times, nurses about once, RTs never. Nurses spend a quarter of their steps on the monitor. RTs live in assessment and communication. That's the hypothesis on your slide, measured."
- Section 02: "Here's where people leave the standard. These bars are the opportunity areas for a CDS prompt. For RTs it's the hand-off at the start. For providers it's calling for help."
- Section 03: "And COMET. Sessions that looked at the risk score reached the rescue about 14 seconds faster, and patients were unstable for less time. It also shows placement: COMET gets viewed about six seconds after the change, and about half go straight to the patient afterwards."
- Say it plainly: "This is simulated data built around your hypothesis. It proves the method. With your real logs it gives the real answer."

**1:50 · Report Card, then Cohort (30 s)**
- Report Card: "For Maya, the last tile is her RN workflow match, 75 to 83 percent. The history table marks the session where she used COMET, attempt 3, which is also her best score."
- Cohort: "For educators, the workflow match line by role and attempt. It tells you whether practice makes people work more like the standard."

**2:20 · Data & Pipeline (25 s)**
"Each log line goes to one lane by a simple rule in one config file. Add a new information source, say a second screen, and it's one line. Point the pipeline at real DISCOVER logs and every page updates."

**2:45 · Close (15 s)**
"What we need from you: confirm the lane rules, confirm the three standard workflows, and a few real sessions with roles. Then we can tell you where COMET should sit in each role's workflow."

## If you only have 2 minutes

Skip Report Card, Cohort and Data. Go Overview → Workflow map (Session Replay 04) → Role Workflows 01, 02, 03 → close.

## Likely questions

- **Is the data real?** No. It's simulated and labelled on screen. Each learner has a role and a hidden behaviour profile, and half the sessions have COMET switched on. The pipeline reads the same format DISCOVER would export.
- **How do you find the standard workflow?** For each role we compare every session's path with every other one (edit distance: how many steps you'd add, remove or swap). The standard is the session closest to all the others. It's always a real path someone took, not an average no one did.
- **Why leave COMET out of the standard?** So the standard is the workflow without the tool. Then any change when COMET is used shows up as a difference.
- **Is the COMET effect causal?** Not from this. In the sample, COMET is randomly available, so it's closer to a trial, but on real data you'd want COMET randomised per session to make that claim.
- **What does "skipped a step" mean?** The standard step has no matching step, in order, in the learner's path (longest common subsequence).
- **Where do target times and rules come from?** Placeholders. The clinical team edits them in `lens/catalog.py`.
- **Why Elo for ratings?** No training data needed, updates after every action, explainable in one sentence.
- **What's next?** Real logs with roles, validate the lanes and standards with the team, then test COMET placements by role.

## Backup plan

Record a 2-minute screen capture of the demo path beforehand. If wifi or the laptop fails, play the video.
