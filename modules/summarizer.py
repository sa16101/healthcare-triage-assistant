"""Structured information summary (rule-based) with optional LLM rewrite guarded by a safety filter."""
import json
import os
import re

SAFETY_FILTER = re.compile(
    r"\b(diagnos\w*|prescrib\w*|you (?:have|should)|suffering from|likely (?:has|have)|probably|suspected|rule out|"
    r"treatment|therapy|dosage|take (?:a |the )?(?:tablet|medicine|antibiotic)|consistent with|suggestive of|caused by)\b", re.I)


def llm_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def call_llm(system: str, user: str, max_tokens: int = 350):
    """OpenAI-compatible chat API. Returns (text|None, status_message). Never raises."""
    if not llm_configured():
        return None, "LLM not configured (set LLM_API_KEY) - using rule-based output."
    try:
        import requests
        base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        r = requests.post(f"{base}/chat/completions", timeout=20,
                          headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                          json={"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "max_tokens": max_tokens, "temperature": 0.2,
                                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip(), "LLM response received."
    except Exception as e:  # noqa: BLE001
        return None, f"LLM unavailable ({e.__class__.__name__}) - using rule-based output."


def _join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def find_missing(patient: dict, ex: dict, text: str = "") -> list:
    """Returns [{'key','label'}] of information that was not provided."""
    present = [s for s in ex["symptoms"] if not s["negated"]]
    names = {s["name"] for s in present}
    m = []
    if "fever" in names and not ex["temp_f"]:
        m.append(("temperature", "Highest recorded temperature"))
    if not ex["overall_duration"]:
        m.append(("duration", "Symptom onset / duration"))
    if not ex["conditions"] and not ex["conditions_denied"]:
        m.append(("conditions", "Existing medical conditions"))
    if not ex["medications"] and not ex["meds_denied"]:
        m.append(("medications", "Current medications"))
    if not ex["progression"]:
        m.append(("progression", "Whether symptoms are getting better or worse"))
    if present and not any(s["severity"] for s in present):
        m.append(("severity", "Severity of symptoms"))
    if len(present) < 3:
        m.append(("additional", "Additional relevant symptoms"))
    if not ex["vitals"]:
        m.append(("vitals", "Vital signs (BP, pulse, SpO2, respiratory rate)"))
    if patient.get("gender") == "Female" and 12 <= (patient.get("age") or 0) <= 50 and "pregnancy" not in ex["conditions"]:
        m.append(("pregnancy", "Pregnancy status (if applicable)"))
    return [{"key": k, "label": l} for k, l in m]


def build_summary(patient: dict, ex: dict, report: dict | None, missing: list, original: str, english: str,
                  use_llm: bool = False) -> dict:
    present = [s for s in ex["symptoms"] if not s["negated"]]
    denied = [s["name"] for s in ex["symptoms"] if s["negated"]]
    dur = ex["overall_duration"]
    who = f"{patient.get('age')}-year-old {str(patient.get('gender', '')).lower()} patient".replace("0-year-old", "infant (<1 year)")
    if present:
        narrative = f"{who.capitalize()} reports {_join(s['name'] for s in present)}" + (f" for approximately {dur[0]}." if dur else ".")
    else:
        narrative = f"{who.capitalize()}; no symptoms could be extracted from the input."
    if denied:
        narrative += f" Patient denies {_join(denied)}."
    if ex["temp_f"]:
        narrative += f" Highest recorded temperature mentioned: {ex['temp_f']:g} °F."
    if report and report["tests"]:
        narrative += f" Uploaded report lists {len(report['tests'])} value(s), {report['abnormal_count']} flagged by the report."

    reported = []
    for s in ex["symptoms"]:
        bits = [b for b in (f"duration {s['duration']}" if s["duration"] else "", f"severity {s['severity']}" if s["severity"] else "") if b]
        reported.append(f"{s['name'].capitalize()}: {'No (denied)' if s['negated'] else 'Yes'}" + (f" ({', '.join(bits)})" if bits and not s["negated"] else ""))
    timeline = (f"Symptom duration reported as approximately {dur[0]}." if dur else "Onset / duration not stated.")
    if ex["progression"]:
        timeline += f" Progression: {ex['progression']}."
    rep_lines = ["No report uploaded."]
    if report and report["tests"]:
        rep_lines = ([f"Report date: {report['date']}"] if report["date"] else []) + [
            f"{t['test']}: {t['value']:g} {t['unit']}".strip() + (f" (ref {t['reference']})" if t["reference"] else "")
            + (f" - {t['flag'].upper()}" if t["abnormal"] else "") for t in report["tests"]]
    elif report is not None:
        rep_lines = ["Report text provided but no test values could be parsed."]
    source, status = "rule-based template", ""
    if use_llm:
        facts = {"patient": who, "symptoms": reported, "timeline": timeline, "observations": ex["observations"],
                 "report_values": rep_lines, "missing": [m["label"] for m in missing]}
        txt, status = call_llm(
            "You are a documentation assistant for healthcare staff. Rewrite the given facts as a neutral 3-5 sentence summary. "
            "Use ONLY the facts provided. Never diagnose, suggest causes, name diseases not stated, recommend treatment or medicines. "
            "Say 'not stated' for unknowns.", json.dumps(facts, ensure_ascii=False))
        if txt and SAFETY_FILTER.search(txt):
            status = "LLM output rejected by safety filter (diagnostic / treatment wording) - using rule-based summary."
        elif txt:
            narrative, source = txt, "LLM (passed safety filter)"
    return {"overview": f"Patient ID {patient.get('patient_id')} · {patient.get('age')} yrs · {patient.get('gender')} · "
                        f"{patient.get('language')} · {patient.get('facility_type')}",
            "narrative": narrative, "narrative_source": source, "llm_status": status, "reported_symptoms": reported,
            "timeline": timeline, "report_info": rep_lines, "missing": [m["label"] for m in missing],
            "observations": ex["observations"] or ["No additional observations extracted."]}
