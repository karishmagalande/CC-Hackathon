"""
Static reference data for DISCOVER Lens.

Everything an educator might want to tune lives here: the room layout, the
competency model, the scenarios and the rules that turn raw headset
interactions into clinical critical actions.

The clinical targets below are placeholder values for a prototype. They should
be replaced with the DISCOVER team's own scenario definitions.
"""

# ---------------------------------------------------------------------------
# Room layout (top-down, metres). Origin is the corner by the door.
# Matches the inpatient room used in the DISCOVER infant scenarios.
# ---------------------------------------------------------------------------
ROOM_SIZE = (6.0, 5.0)

ROOM_OBJECTS = {
    "patient":   {"label": "Patient (crib)",   "xy": (3.0, 2.6), "group": "patient"},
    "monitor":   {"label": "Bedside monitor",  "xy": (3.0, 4.75), "group": "monitor"},
    "phone":     {"label": "Room phone",       "xy": (5.7, 4.3), "group": "equipment"},
    "bvm":       {"label": "Bag-valve mask",   "xy": (1.3, 4.75), "group": "equipment"},
    "o2_flow":   {"label": "O2 flowmeter",     "xy": (2.1, 4.8), "group": "equipment"},
    "suction":   {"label": "Wall suction",     "xy": (3.9, 4.8), "group": "equipment"},
    "iv_pump":   {"label": "IV pump",          "xy": (4.4, 2.0), "group": "equipment"},
    "vent":      {"label": "Ventilator",       "xy": (5.0, 3.2), "group": "equipment"},
    "med_cart":  {"label": "Med cart",         "xy": (0.8, 1.4), "group": "equipment"},
    "penlight":  {"label": "Penlight",         "xy": (3.0, 2.6), "group": "equipment"},
    "clock":     {"label": "Wall clock",       "xy": (4.6, 4.95), "group": "environment"},
    "door":      {"label": "Door",             "xy": (0.4, 0.05), "group": "environment"},
    "sink":      {"label": "Sink",             "xy": (5.5, 0.6), "group": "environment"},
    "elsewhere": {"label": "Elsewhere",        "xy": (1.5, 0.3), "group": "environment"},
    "epic":      {"label": "Epic workstation", "xy": (0.6, 2.9), "group": "equipment"},
    "comet":     {"label": "COMET screen",     "xy": (3.7, 4.95), "group": "monitor"},
}

# ---------------------------------------------------------------------------
# Workflow lanes: where a clinician gathers information. Same lanes, order and
# colours as the hackathon team's VR observation swim-lane maps.
# ---------------------------------------------------------------------------
LANES = {
    "epic":          {"label": "Epic",                 "color": "#2F8FEA", "order": 1},
    "assessment":    {"label": "Patient assessment",   "color": "#D6145F", "order": 2},
    "vitals":        {"label": "Vital sign monitor",   "color": "#86C440", "order": 3},
    "comet":         {"label": "COMET / in-room view", "color": "#9B1FAF", "order": 4},
    "communication": {"label": "Communication",        "color": "#8FD3F4", "order": 5},
}
LANE_ORDER = sorted(LANES, key=lambda k: LANES[k]["order"])

# Role colours as used on the team's "Three Typical Workflows" slide
ROLE_COLORS = {"Provider": "#6E9FE8", "RN": "#2BAA7A", "RT": "#E0651A"}

# Hypothesised standard path per role, read from the team's slide 3.
# The pipeline also computes each role's typical path from the session data.
ROLE_WORKFLOWS = {
    "Provider": ["communication", "epic", "assessment", "vitals", "communication", "assessment", "epic",
                 "communication"],
    "RN": ["communication", "epic", "assessment", "communication", "epic", "assessment", "communication", "epic"],
    "RT": ["communication", "assessment", "communication", "epic", "communication", "assessment", "communication"],
}

ROLE_SUMMARY = {
    "Provider": "Look at the bigger picture to assess the patient's trajectory. Gather as much information as "
                "possible before entering the room.",
    "RN": "Present in the room to provide continuous care. Rely on vitals, trends and patient assessment.",
    "RT": "Always on the go and focused on respiratory needs. Enter the room to check respiratory equipment "
          "and assess the patient.",
}


def event_lane(verb, obj):
    """Which information lane a logged interaction belongs to (None = not an information step)."""
    if obj == "epic":
        return "epic"
    if obj == "comet":
        return "comet"
    if obj in ("team", "phone") and verb in ("communicate", "use"):
        return "communication"
    if obj == "monitor" and verb == "check":
        return "vitals"
    if obj in ("patient", "penlight"):
        return "assessment"
    if verb == "inspect":
        return "assessment"
    return None

GAZE_GROUPS = ["patient", "monitor", "equipment", "environment"]

# Equipment with an on-screen or physical control surface. Used for the
# partner "friction" view: which controls get touched without effect.
CONTROL_SURFACES = {
    "o2_flow":  ["flow_knob", "outlet_valve"],
    "vent":     ["mode_dial", "fio2_knob", "start_button", "alarm_silence"],
    "iv_pump":  ["channel_select", "rate_entry", "volume_entry", "start_button"],
    "suction":  ["pressure_dial", "on_switch"],
    "phone":    ["keypad", "speed_dial_help"],
    "med_cart": ["drawer_2", "drawer_3", "drawer_4"],
}

# ---------------------------------------------------------------------------
# Competency model
# ---------------------------------------------------------------------------
COMPETENCIES = {
    "REC": "Recognition",
    "COM": "Communication",
    "AIR": "Airway & Breathing",
    "CIR": "Circulation & Meds",
    "EQP": "Equipment Fluency",
}

# ---------------------------------------------------------------------------
# Scenarios
#   onset_range   seconds after start when the patient begins to deteriorate
#   rescue        action id that reverses the deterioration
#   expert_sec    expert time to complete the action, seconds after onset
#   target_sec    full credit if completed within this many seconds of onset
#   rule          raw interaction that counts as completing the action
#   difficulty    starting rating for the scenario (Elo scale)
# ---------------------------------------------------------------------------
SCENARIOS = {
    "SC01": {
        "name": "Infant Respiratory Decompensation",
        "short": "Resp. decompensation",
        "patient": "6 month old, bronchiolitis, progresses to apnea",
        "duration": 300, "onset_range": (25, 45), "difficulty": 1450,
        "rescue": "start_bvm",
        "vitals": {
            "baseline": {"hr": 150, "spo2": 95, "rr": 48, "sbp": 88},
            "nadir":    {"hr": 82, "spo2": 68, "rr": 4, "sbp": 70},
            "tau_decline": 55, "tau_recover": 22,
        },
        "danger": {"spo2_lt": 90, "hr_lt": 100, "hr_gt": 190, "sbp_lt": 70},
        "actions": [
            {"id": "assess_patient", "label": "Hands-on assessment", "comp": "REC",
             "expert_sec": 5, "target_sec": 20, "weight": 15,
             "rule": {"verb": "touch", "object": "patient", "target": "chest"}},
            {"id": "call_help", "label": "Call for help", "comp": "COM",
             "expert_sec": 14, "target_sec": 35, "weight": 15,
             "rule": {"verb": "use", "object": "phone", "target": "speed_dial_help"}},
            {"id": "position_airway", "label": "Reposition airway", "comp": "AIR",
             "expert_sec": 20, "target_sec": 45, "weight": 15,
             "rule": {"verb": "manipulate", "object": "patient", "target": "head_tilt"}},
            {"id": "start_bvm", "label": "Start bag-mask ventilation", "comp": "AIR",
             "expert_sec": 28, "target_sec": 60, "weight": 25,
             "rule": {"verb": "attach", "object": "bvm", "target": "patient_face"}},
            {"id": "connect_o2", "label": "Connect O2 to BVM", "comp": "EQP",
             "expert_sec": 36, "target_sec": 75, "weight": 15,
             "rule": {"verb": "set", "object": "o2_flow", "target": "flow_knob"}},
            {"id": "check_pupils", "label": "Neuro check (pupils)", "comp": "REC",
             "expert_sec": 70, "target_sec": 130, "weight": 15,
             "rule": {"verb": "use", "object": "penlight", "target": "patient_eyes"}},
        ],
    },
    "SC02": {
        "name": "Infant Status Epilepticus",
        "short": "Status epilepticus",
        "patient": "9 month old, febrile, prolonged seizure",
        "duration": 300, "onset_range": (20, 35), "difficulty": 1520,
        "rescue": "give_benzo",
        "vitals": {
            "baseline": {"hr": 140, "spo2": 98, "rr": 36, "sbp": 90},
            "nadir":    {"hr": 195, "spo2": 82, "rr": 12, "sbp": 104},
            "tau_decline": 50, "tau_recover": 30,
        },
        "danger": {"spo2_lt": 90, "hr_gt": 180, "hr_lt": 90, "sbp_lt": 65},
        "actions": [
            {"id": "assess_patient", "label": "Hands-on assessment", "comp": "REC",
             "expert_sec": 4, "target_sec": 15, "weight": 10,
             "rule": {"verb": "touch", "object": "patient", "target": "chest"}},
            {"id": "note_time", "label": "Note seizure start time", "comp": "COM",
             "expert_sec": 8, "target_sec": 25, "weight": 10,
             "rule": {"verb": "look_confirm", "object": "clock", "target": "clock_face"}},
            {"id": "call_help", "label": "Call for help", "comp": "COM",
             "expert_sec": 12, "target_sec": 35, "weight": 15,
             "rule": {"verb": "use", "object": "phone", "target": "speed_dial_help"}},
            {"id": "apply_o2", "label": "Apply oxygen", "comp": "AIR",
             "expert_sec": 24, "target_sec": 60, "weight": 15,
             "rule": {"verb": "set", "object": "o2_flow", "target": "flow_knob"}},
            {"id": "suction_airway", "label": "Suction airway", "comp": "AIR",
             "expert_sec": 40, "target_sec": 90, "weight": 15,
             "rule": {"verb": "set", "object": "suction", "target": "on_switch"}},
            {"id": "give_benzo", "label": "First-line anticonvulsant", "comp": "CIR",
             "expert_sec": 75, "target_sec": 150, "weight": 35,
             "rule": {"verb": "administer", "object": "med_cart", "target": "drawer_3"}},
        ],
    },
    "SC03": {
        "name": "Toddler Septic Shock",
        "short": "Septic shock",
        "patient": "2 year old, fever, poor perfusion",
        "duration": 330, "onset_range": (30, 50), "difficulty": 1580,
        "rescue": "fluid_bolus",
        "vitals": {
            "baseline": {"hr": 130, "spo2": 97, "rr": 30, "sbp": 92},
            "nadir":    {"hr": 205, "spo2": 90, "rr": 52, "sbp": 58},
            "tau_decline": 70, "tau_recover": 40,
        },
        "danger": {"spo2_lt": 90, "hr_gt": 180, "sbp_lt": 70},
        "actions": [
            {"id": "assess_patient", "label": "Hands-on assessment", "comp": "REC",
             "expert_sec": 6, "target_sec": 20, "weight": 10,
             "rule": {"verb": "touch", "object": "patient", "target": "chest"}},
            {"id": "cap_refill", "label": "Check capillary refill", "comp": "REC",
             "expert_sec": 12, "target_sec": 35, "weight": 15,
             "rule": {"verb": "touch", "object": "patient", "target": "nail_bed"}},
            {"id": "call_help", "label": "Call for help", "comp": "COM",
             "expert_sec": 18, "target_sec": 45, "weight": 15,
             "rule": {"verb": "use", "object": "phone", "target": "speed_dial_help"}},
            {"id": "program_pump", "label": "Program IV pump", "comp": "EQP",
             "expert_sec": 45, "target_sec": 100, "weight": 20,
             "rule": {"verb": "set", "object": "iv_pump", "target": "start_button"}},
            {"id": "fluid_bolus", "label": "Start fluid bolus", "comp": "CIR",
             "expert_sec": 55, "target_sec": 120, "weight": 25,
             "rule": {"verb": "administer", "object": "iv_pump", "target": "bolus_line"}},
            {"id": "reassess", "label": "Reassess after bolus", "comp": "REC",
             "expert_sec": 110, "target_sec": 200, "weight": 15,
             "rule": {"verb": "touch", "object": "patient", "target": "nail_bed_recheck"}},
        ],
    },
    "SC04": {
        "name": "Anaphylaxis After Antibiotic",
        "short": "Anaphylaxis",
        "patient": "7 year old, new rash and wheeze after first dose",
        "duration": 280, "onset_range": (20, 40), "difficulty": 1400,
        "rescue": "give_epi",
        "vitals": {
            "baseline": {"hr": 100, "spo2": 98, "rr": 22, "sbp": 102},
            "nadir":    {"hr": 165, "spo2": 84, "rr": 40, "sbp": 66},
            "tau_decline": 45, "tau_recover": 25,
        },
        "danger": {"spo2_lt": 90, "hr_gt": 150, "sbp_lt": 75},
        "actions": [
            {"id": "assess_patient", "label": "Hands-on assessment", "comp": "REC",
             "expert_sec": 4, "target_sec": 15, "weight": 10,
             "rule": {"verb": "touch", "object": "patient", "target": "chest"}},
            {"id": "stop_infusion", "label": "Stop antibiotic infusion", "comp": "EQP",
             "expert_sec": 9, "target_sec": 25, "weight": 15,
             "rule": {"verb": "set", "object": "iv_pump", "target": "channel_select"}},
            {"id": "call_help", "label": "Call for help", "comp": "COM",
             "expert_sec": 15, "target_sec": 40, "weight": 15,
             "rule": {"verb": "use", "object": "phone", "target": "speed_dial_help"}},
            {"id": "give_epi", "label": "Give IM epinephrine", "comp": "CIR",
             "expert_sec": 30, "target_sec": 75, "weight": 35,
             "rule": {"verb": "administer", "object": "med_cart", "target": "drawer_2"}},
            {"id": "apply_o2", "label": "Apply oxygen", "comp": "AIR",
             "expert_sec": 40, "target_sec": 90, "weight": 15,
             "rule": {"verb": "set", "object": "o2_flow", "target": "flow_knob"}},
            {"id": "position_patient", "label": "Position patient", "comp": "AIR",
             "expert_sec": 50, "target_sec": 110, "weight": 10,
             "rule": {"verb": "manipulate", "object": "patient", "target": "supine_legs_up"}},
        ],
    },
    "SC05": {
        "name": "Post-op Hypoventilation",
        "short": "Hypoventilation",
        "patient": "4 year old, post-op day 0, oversedated",
        "duration": 300, "onset_range": (30, 50), "difficulty": 1500,
        "rescue": "vent_support",
        "vitals": {
            "baseline": {"hr": 115, "spo2": 96, "rr": 22, "sbp": 96},
            "nadir":    {"hr": 78, "spo2": 76, "rr": 5, "sbp": 80},
            "tau_decline": 65, "tau_recover": 30,
        },
        "danger": {"spo2_lt": 90, "hr_lt": 80, "sbp_lt": 70},
        "actions": [
            {"id": "assess_patient", "label": "Hands-on assessment", "comp": "REC",
             "expert_sec": 6, "target_sec": 20, "weight": 10,
             "rule": {"verb": "touch", "object": "patient", "target": "chest"}},
            {"id": "check_pupils", "label": "Neuro check (pupils)", "comp": "REC",
             "expert_sec": 12, "target_sec": 35, "weight": 15,
             "rule": {"verb": "use", "object": "penlight", "target": "patient_eyes"}},
            {"id": "call_help", "label": "Call for help", "comp": "COM",
             "expert_sec": 16, "target_sec": 40, "weight": 15,
             "rule": {"verb": "use", "object": "phone", "target": "speed_dial_help"}},
            {"id": "stop_opioid", "label": "Pause opioid infusion", "comp": "EQP",
             "expert_sec": 22, "target_sec": 55, "weight": 15,
             "rule": {"verb": "set", "object": "iv_pump", "target": "channel_select"}},
            {"id": "vent_support", "label": "Start ventilatory support", "comp": "AIR",
             "expert_sec": 35, "target_sec": 80, "weight": 30,
             "rule": {"verb": "set", "object": "vent", "target": "start_button"}},
            {"id": "reversal_agent", "label": "Prepare reversal agent", "comp": "CIR",
             "expert_sec": 60, "target_sec": 130, "weight": 15,
             "rule": {"verb": "administer", "object": "med_cart", "target": "drawer_4"}},
        ],
    },
}

ROLES = ["Provider", "Provider", "RN", "RN", "RN", "RT", "RT"]
UNITS = ["A6 Central", "A5 South", "PICU", "CICU", "Hospital Medicine", "Surgery"]


def action_map(scenario_id):
    """Return {action_id: action dict} for a scenario."""
    return {a["id"]: a for a in SCENARIOS[scenario_id]["actions"]}


def object_xy(obj):
    return ROOM_OBJECTS.get(obj, ROOM_OBJECTS["elsewhere"])["xy"]


def object_group(obj):
    return ROOM_OBJECTS.get(obj, ROOM_OBJECTS["elsewhere"])["group"]
