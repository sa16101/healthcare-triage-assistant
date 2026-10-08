"""Transparent rule-based urgency flagging. Thresholds are ILLUSTRATIVE and must be validated by clinicians.
The engine never names a disease or diagnosis: it only says which predefined rule fired and why."""
import re
from modules.symptom_processor import present

LABELS = {"URGENT": "🔴 URGENT REVIEW", "REVIEW": "🟡 REVIEW REQUIRED", "LOW": "🟢 LOW PRIORITY"}
CATEGORY = {"URGENT": "URGENT REVIEW", "REVIEW": "REVIEW REQUIRED", "LOW": "LOW PRIORITY"}
ACTIONS = {"URGENT": "Immediate review by a qualified healthcare professional.",
           "REVIEW": "Review by qualified healthcare staff.",
           "LOW": "Routine review by qualified healthcare staff when available."}
FLAG_DISCLAIMER = "This is an urgency-support flag, not a medical diagnosis."
URGENT_SYMPTOMS = {"chest pain", "breathlessness", "loss of consciousness", "seizure", "confusion",
                   "slurred speech / facial droop", "self-harm statement"}
CHRONIC = {"diabetes", "hypertension", "asthma / chronic lung disease", "heart disease", "kidney disease",
           "tuberculosis", "cancer"}
LOW_OK = {"cough", "cold / runny nose", "sore throat", "headache", "body pain", "joint pain", "fatigue",
          "weakness", "rash / itching", "loss of appetite"}
CRITICAL_LABS = [  # (display, name regex, predicate(value, unit), description)
    ("Hemoglobin", r"h(?:a)?emoglobin|\bhb\b", lambda v, u: v < 7, "< 7 g/dL"),
    ("Platelet count", r"platelet", lambda v, u: (v * 100000 if "lakh" in u else v * 1000 if v < 1000 else v) < 20000, "< 20,000 /µL"),
    ("Blood glucose", r"glucose|blood sugar|\bfbs\b|\brbs\b|\bppbs\b", lambda v, u: v >= 400 and "mmol" not in u, ">= 400 mg/dL"),
    ("Potassium", r"potassium", lambda v, u: v < 2.5 or v > 6.5, "< 2.5 or > 6.5 mmol/L"),
    ("Sodium", r"sodium", lambda v, u: v < 120 or v > 160, "< 120 or > 160 mmol/L"),
    ("Serum creatinine", r"creatinine", lambda v, u: v >= 5.0, ">= 5.0 mg/dL"),
]


def _days(c, names=None):
    return max([s["duration_days"] or 0 for s in c["syms"] if not s["negated"] and (names is None or s["name"] in names)] +
               [0 if names else (c["ex"]["overall_duration"] or ("", 0))[1]])


def _u_symptoms(c):
    hit = sorted(URGENT_SYMPTOMS & c["present"])
    return f"{', '.join(hit)} reported; listed as urgent-review symptom(s) in the rule set." if hit else None


def _u_bleed(c):
    if "bleeding" in c["present"] and (any(s["name"] == "bleeding" and s["severity"] == "severe" for s in c["syms"])
                                       or re.search(r"heavy|profuse|vomiting blood|coughing (?:up )?blood", c["text"])):
        return "Bleeding described as heavy or involving vomited/coughed blood."


def _u_temp(c):
    t = c["ex"]["temp_f"]
    return f"Recorded temperature {t:g} °F is at or above the 104 °F urgent threshold." if t and t >= 104 else None


def _u_infant(c):
    if c["age"] is not None and c["age"] <= 1 and ({"fever", "poor feeding / drinking", "vomiting", "diarrhoea", "breathlessness"} & c["present"]):
        return "Infant (age <= 1 year) with fever, feeding difficulty, vomiting, diarrhoea or breathing symptoms."


def _u_vitals(c):
    v, out = c["ex"]["vitals"], []
    if v.get("spo2") is not None and v["spo2"] < 92:
        out.append(f"SpO2 {v['spo2']}% is below 92%")
    if v.get("sbp") and (v["sbp"] >= 180 or v["dbp"] >= 120 or v["sbp"] < 90):
        out.append(f"blood pressure {v['sbp']}/{v['dbp']} is outside the urgent threshold range")
    if v.get("pulse") and (v["pulse"] > 130 or v["pulse"] < 40):
        out.append(f"pulse {v['pulse']} is outside the 40-130 range")
    return ("; ".join(out) + ".")[0].upper() + ("; ".join(out) + ".")[1:] if out else None


def _critical_labs(c):
    out = []
    for t in (c["report"] or {}).get("tests", []):
        for disp, rx, pred, desc in CRITICAL_LABS:
            if re.search(rx, t["test"].lower()) and pred(t["value"], (t.get("unit") or "").lower()):
                out.append(f"{disp} {t['value']:g} {t.get('unit') or ''} (critical-value rule {desc})")
    return "Report value(s) meet critical-value rules: " + "; ".join(out) + "." if out else None


def _r_temp(c):
    t = c["ex"]["temp_f"]
    return f"Recorded temperature {t:g} °F is at or above 101 °F." if t and t >= 101 else None


def _r_fever_days(c):
    return "Fever reported for 3 or more days." if "fever" in c["present"] and _days(c, {"fever"}) >= 3 or (
        "fever" in c["present"] and c["ex"]["overall_duration"] and c["ex"]["overall_duration"][1] >= 3) else None


def _r_fever_notemp(c):
    return "Fever reported without a recorded temperature." if "fever" in c["present"] and not c["ex"]["temp_f"] else None


def _r_long(c):
    return "Symptoms reported for 7 or more days." if _days(c) >= 7 else None


def _r_severe(c):
    s = [x["name"] for x in c["syms"] if x["severity"] == "severe" and not x["negated"]]
    return f"Severe intensity mentioned for: {', '.join(s)}." if s else None


def _r_prog(c):
    p = c["ex"]["progression"]
    return f"Symptoms described as {p}." if p in ("worsening", "not improving") else None


def _r_age(c):
    a = c["age"]
    if c["present"] and a is not None and (a <= 5 or a >= 65):
        return f"Age {a}: young children and older adults are routed to review for any reported symptom."


def _r_preg(c):
    if c["present"] and "pregnancy" in c["ex"]["conditions"]:
        return "Pregnancy mentioned together with reported symptoms."


def _r_chronic(c):
    ch = sorted(CHRONIC & set(c["ex"]["conditions"]))
    return f"Existing condition(s) mentioned ({', '.join(ch)}) together with reported symptoms." if ch and c["present"] else None


def _r_gi(c):
    if {"vomiting", "diarrhoea"} & c["present"] and _days(c, {"vomiting", "diarrhoea"}) >= 2:
        return "Vomiting or diarrhoea reported for 2 or more days."


def _r_bleed(c):
    return "Bleeding reported." if "bleeding" in c["present"] else None


def _r_labs(c):
    ab = [t for t in (c["report"] or {}).get("tests", []) if t["abnormal"]]
    return f"Uploaded report has {len(ab)} flagged value(s): " + ", ".join(f"{t['test']} ({t['flag']})" for t in ab[:6]) + "." if ab else None


def _r_vitals(c):
    v, out = c["ex"]["vitals"], []
    if v.get("spo2") is not None and 92 <= v["spo2"] < 95:
        out.append(f"SpO2 {v['spo2']}%")
    if v.get("sbp") and (v["sbp"] >= 140 or v["dbp"] >= 90):
        out.append(f"BP {v['sbp']}/{v['dbp']}")
    return "Vitals outside usual range: " + ", ".join(out) + "." if out else None


def _r_many(c):
    return f"{len(c['present'])} distinct symptoms reported (3 or more)." if len(c["present"]) >= 3 else None


def _r_other(c):
    o = sorted(c["present"] - LOW_OK - {"fever"})
    return f"Symptom(s) outside the low-priority rule set: {', '.join(o)}." if o else None


RULES = [  # (id, level, catalogue description, function)
    ("U1", "URGENT", "Chest pain, breathing difficulty, loss of consciousness, seizure, confusion, stroke-like signs or self-harm statement", _u_symptoms),
    ("U2", "URGENT", "Heavy bleeding or vomited / coughed blood", _u_bleed),
    ("U3", "URGENT", "Recorded temperature >= 104 °F", _u_temp),
    ("U4", "URGENT", "Infant (<= 1 yr) with fever, poor feeding, vomiting, diarrhoea or breathing symptoms", _u_infant),
    ("U5", "URGENT", "SpO2 < 92%, BP >= 180/120 or SBP < 90, pulse > 130 or < 40", _u_vitals),
    ("U6", "URGENT", "Critical lab values (e.g. Hb < 7, platelets < 20,000, glucose >= 400, K+ / Na+ extremes, creatinine >= 5)", _critical_labs),
    ("R1", "REVIEW", "Recorded temperature >= 101 °F", _r_temp),
    ("R2", "REVIEW", "Fever for >= 3 days", _r_fever_days),
    ("R3", "REVIEW", "Fever without a recorded temperature (safety-first)", _r_fever_notemp),
    ("R4", "REVIEW", "Any symptom for >= 7 days", _r_long),
    ("R5", "REVIEW", "Severe intensity mentioned", _r_severe),
    ("R6", "REVIEW", "Worsening / not improving", _r_prog),
    ("R7", "REVIEW", "Age <= 5 or >= 65 with any symptom", _r_age),
    ("R8", "REVIEW", "Pregnancy mentioned with symptoms", _r_preg),
    ("R9", "REVIEW", "Chronic condition mentioned with symptoms", _r_chronic),
    ("R10", "REVIEW", "Vomiting / diarrhoea for >= 2 days", _r_gi),
    ("R11", "REVIEW", "Any bleeding", _r_bleed),
    ("R12", "REVIEW", "Flagged (abnormal) values in uploaded report", _r_labs),
    ("R13", "REVIEW", "SpO2 92-94%, BP >= 140/90", _r_vitals),
    ("R14", "REVIEW", "3 or more distinct symptoms", _r_many),
    ("R15", "REVIEW", "Symptom outside the low-priority list", _r_other),
]


def describe_rules():
    return [{"Rule": i, "Level": CATEGORY[l], "Trigger": d} for i, l, d, _ in RULES]


def evaluate(patient: dict, ex: dict, report: dict | None, text_en: str = "") -> dict:
    c = {"age": patient.get("age"), "ex": ex, "syms": ex["symptoms"], "present": set(present(ex)),
         "report": report, "text": (text_en or "").lower()}
    fired = []
    for rid, lvl, _d, fn in RULES:
        try:
            msg = fn(c)
        except Exception:  # a broken rule must never crash triage; fail safe by escalating review
            msg, lvl = f"Rule {rid} could not be evaluated; manual review advised.", "REVIEW"
        if msg:
            fired.append((rid, lvl, msg))
    if not c["present"] and not any(l == "URGENT" for _, l, _m in fired):
        fired.append(("D0", "REVIEW", "No symptom could be extracted from the input, so the rules cannot be applied reliably."))
    level = "URGENT" if any(l == "URGENT" for _, l, _m in fired) else "REVIEW" if fired else "LOW"
    fired.sort(key=lambda f: f[1] != "URGENT")
    reasons = [f"[{rid}] {m}" for rid, _l, m in fired] or [
        "No urgent-review or review-required rule was triggered by the information provided (this does not rule out a health concern)."]
    return {"level": level, "category": CATEGORY[level], "label": LABELS[level], "reasons": reasons,
            "rules_triggered": [f[0] for f in fired], "recommended_action": ACTIONS[level],
            "disclaimer": FLAG_DISCLAIMER}
