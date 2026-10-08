"""Privacy helpers: validation, PII redaction, and a role-based access *mockup* (not real authentication)."""
import re

PID_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{3,19}$")
PII_PATTERNS = {
    "Aadhaar-like number": re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)"),
    "phone number": re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"),
    "email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "name statement": re.compile(r"\b(?:my name is|i am called)\s+[A-Za-z]+(?:\s+[A-Za-z]+)?", re.I),
}
GENDERS = ["Female", "Male", "Other", "Prefer not to say"]
LANGUAGES = ["English", "Hindi"]

ROLE_PERMISSIONS = {
    "Health Worker": {"create", "view_dashboard", "request_info"},
    "Nurse": {"create", "view_dashboard", "request_info", "mark_reviewed", "escalate", "edit_note"},
    "Medical Officer": {"create", "view_dashboard", "request_info", "mark_reviewed", "escalate", "edit_note"},
    "Auditor": {"view_dashboard", "view_audit"},
}
PERM_LABELS = {"create": "Create assessments", "view_dashboard": "View dashboard & cases", "request_info": "Request more information",
               "mark_reviewed": "Mark reviewed", "escalate": "Escalate", "edit_note": "Edit triage note", "view_audit": "View audit log"}


def redact_pii(text: str):
    """Returns (clean_text, list_of_pii_types_found)."""
    found = []
    for label, rx in PII_PATTERNS.items():
        if rx.search(text or ""):
            found.append(label)
            text = rx.sub(f"[REDACTED {label.upper()}]", text)
    return text, found


def validate_patient(p: dict) -> list:
    errs = []
    if not PID_RE.match(p.get("patient_id") or ""):
        errs.append("Patient ID must be 4-20 characters (A-Z, 0-9, hyphen), e.g. DEMO011. Use a pseudonymous ID, not a real name or number.")
    elif any(rx.search(p["patient_id"]) for rx in (PII_PATTERNS["phone number"], PII_PATTERNS["Aadhaar-like number"])):
        errs.append("Patient ID looks like a phone / Aadhaar number. Please use a pseudonymous ID.")
    age = p.get("age")
    if age is None or not isinstance(age, (int, float)) or not 0 <= age <= 120:
        errs.append("Age must be a number between 0 and 120 (use 0 for infants under 1 year).")
    if p.get("gender") not in GENDERS:
        errs.append("Please select a gender option.")
    if p.get("language") not in LANGUAGES:
        errs.append("Please select a preferred language.")
    if not p.get("facility_type"):
        errs.append("Please select the facility type.")
    if not p.get("consent"):
        errs.append("Consent is required: tick the consent checkbox before continuing.")
    return errs


def current_user() -> dict:
    import streamlit as st
    return st.session_state.get("user") or {"username": "guest", "display_name": "Guest (Health Worker)", "role": "Health Worker"}


def has_perm(perm: str) -> bool:
    return perm in ROLE_PERMISSIONS.get(current_user()["role"], set())
