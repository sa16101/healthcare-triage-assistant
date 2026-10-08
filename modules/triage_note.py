"""Builds the reviewer-facing triage note and runs the full analysis pipeline."""
import datetime as dt
from modules.translator import translate_to_english
from modules.symptom_processor import extract, present
from modules.report_ocr import parse_report
from modules.summarizer import find_missing, build_summary
from modules.question_generator import generate_questions
from modules.risk_engine import evaluate, FLAG_DISCLAIMER
from utils.privacy import redact_pii

NOTE_DISCLAIMER = "This system does not diagnose or prescribe treatment."


def _bul(items):
    return "\n".join(f"- {i}" for i in items) if items else "- None"


def build_note(patient: dict, summary: dict, ex: dict, questions: list, risk: dict) -> str:
    present_s = [s for s in ex["symptoms"] if not s["negated"]]
    sym = [s["name"].capitalize() + (f" ({s['duration']})" if s["duration"] else "") for s in present_s]
    concerns = [summary["narrative"]]
    return f"""TRIAGE SUPPORT NOTE  (AI-generated draft - {dt.datetime.now():%d %b %Y %H:%M})

Patient ID: {patient.get('patient_id')}
Age: {patient.get('age')}
Gender: {patient.get('gender')}
Language: {patient.get('language')}

Chief Concerns:
{_bul(concerns)}

Symptoms:
{_bul(sym)}

Timeline:
- {summary['timeline']}

Report Information:
{_bul(summary['report_info'])}

Missing Information:
{_bul(summary['missing'])}

Follow-up Questions:
{chr(10).join(f"{i}. {q['en']}" for i, q in enumerate(questions, 1)) or '- None'}

Urgency Flag:
- {risk['label']}  ({FLAG_DISCLAIMER})

Reason for Flag:
{_bul(risk['reasons'])}

Reviewer Action:
Pending professional review

Disclaimer:
{NOTE_DISCLAIMER}"""


def analyze_case(patient: dict, symptom_text: str, report_text: str = "", report_name: str = "", use_llm: bool = False) -> dict:
    clean, pii = redact_pii(symptom_text or "")
    english, method, untranslated = translate_to_english(clean)
    ex = extract(english)
    report = parse_report(report_text) if (report_text or "").strip() else None
    missing = find_missing(patient, ex, english)
    questions = generate_questions(patient, ex, missing, use_llm)
    risk = evaluate(patient, ex, report, english)
    summary = build_summary(patient, ex, report, missing, clean, english, use_llm)
    return {"original_text": clean, "pii_redacted": pii, "translated_text": english, "translation_method": method,
            "untranslated": untranslated, "extraction": ex, "report": report, "report_text": report_text or "",
            "report_name": report_name or "", "missing": missing, "questions": questions, "risk": risk,
            "summary": summary, "note": build_note(patient, summary, ex, questions, risk)}
