"""SQLite data layer (synthetic demo data only)."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("TRIAGE_DB_PATH", BASE / "database" / "triage_demo.db"))
STATUSES = ["Pending Review", "Reviewed", "More Info Requested", "Escalated"]
URGENCY_ORDER = {"URGENT REVIEW": 0, "REVIEW REQUIRED": 1, "LOW PRIORITY": 2}
DEMO_USERS = [("asha_hw", "Asha (Demo Health Worker)", "Health Worker"), ("nurse_demo", "Meera (Demo Nurse)", "Nurse"),
              ("dr_demo", "Dr. Rao (Demo Medical Officer)", "Medical Officer"), ("auditor_demo", "Auditor (Demo)", "Auditor")]


class DatabaseError(Exception):
    pass


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def get_conn():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not open the database: {e}") from e
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Database error: {e}") from e
    finally:
        conn.close()


def init_db():
    with get_conn() as c:
        c.executescript((BASE / "database" / "schema.sql").read_text(encoding="utf-8"))
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            c.executemany("INSERT INTO users(username, display_name, role) VALUES (?,?,?)", DEMO_USERS)
        empty = c.execute("SELECT COUNT(*) FROM assessments").fetchone()[0] == 0
    if empty:
        seed_demo()


def seed_demo(csv_path=BASE / "data" / "sample_patients.csv"):
    from modules.triage_note import analyze_case
    df = pd.read_csv(csv_path, encoding="utf-8").fillna("")
    now = datetime.now()
    for i, r in df.iterrows():
        patient = {"patient_id": r.patient_id, "age": int(r.age), "gender": r.gender, "language": r.language,
                   "facility_type": r.facility_type, "consent": True,
                   "assessed_at": (now - timedelta(days=int(r.days_ago), hours=i % 5, minutes=7 * i)).strftime("%Y-%m-%d %H:%M:%S")}
        case = analyze_case(patient, r.symptom_text.replace(" | ", "\n"), r.report_text.replace(" | ", "\n"),
                            "sample_report.png" if r.report_text else "")
        status = r.review_status or "Pending Review"
        reviewer = None if status == "Pending Review" else "Dr. Rao (Demo Medical Officer)"
        aid = save_assessment(patient, case, status=status, reviewer=reviewer,
                              reviewed_at=patient["assessed_at"] if reviewer else None,
                              comment={"Reviewed": "Reviewed; routine advice given by staff.", "More Info Requested": "Please record temperature and current medicines.",
                                       "Escalated": "Escalated to medical officer on duty."}.get(status))
        add_log(aid, "System (seed)", "system", "assessment_created", f"Demo record; flag {case['risk']['category']}")
        if reviewer:
            add_log(aid, reviewer, "Medical Officer", {"Reviewed": "marked_reviewed", "More Info Requested": "requested_more_info", "Escalated": "escalated"}[status], "Demo review action")


def save_assessment(patient, case, edited_note=None, editor=None, status="Pending Review", reviewer=None, reviewed_at=None, comment=None) -> int:
    ts = _now()
    with get_conn() as c:
        c.execute("""INSERT INTO patients(patient_id, age, gender, language, consent, created_at) VALUES (?,?,?,?,?,?)
                     ON CONFLICT(patient_id) DO UPDATE SET age=excluded.age, gender=excluded.gender, language=excluded.language, consent=excluded.consent""",
                  (patient["patient_id"], patient["age"], patient["gender"], patient["language"], int(bool(patient.get("consent"))), ts))
        cur = c.execute("""INSERT INTO assessments(patient_id, facility_type, assessed_at, original_text, translated_text, translation_method,
                           urgency, urgency_reasons, summary, missing_info, questions, review_status, reviewer, reviewed_at, reviewer_comment)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (patient["patient_id"], patient["facility_type"], patient.get("assessed_at") or ts, case["original_text"],
                         case["translated_text"], case["translation_method"], case["risk"]["category"],
                         json.dumps(case["risk"]["reasons"], ensure_ascii=False), json.dumps(case["summary"], ensure_ascii=False),
                         json.dumps(case["summary"]["missing"], ensure_ascii=False), json.dumps(case["questions"], ensure_ascii=False),
                         status, reviewer, reviewed_at, comment))
        aid = cur.lastrowid
        c.executemany("INSERT INTO symptoms(assessment_id, symptom, duration, severity, negated) VALUES (?,?,?,?,?)",
                      [(aid, s["name"], s["duration"], s["severity"], int(s["negated"])) for s in case["extraction"]["symptoms"]])
        if case["report_text"].strip():
            c.execute("INSERT INTO reports(assessment_id, filename, ocr_text, extracted_json, flagged_count) VALUES (?,?,?,?,?)",
                      (aid, case["report_name"], case["report_text"], json.dumps(case["report"], ensure_ascii=False),
                       (case["report"] or {}).get("abnormal_count", 0)))
        c.execute("INSERT INTO triage_notes(assessment_id, ai_note, edited_note, edited_by, edited_at) VALUES (?,?,?,?,?)",
                  (aid, case["note"], edited_note, editor if edited_note else None, ts if edited_note else None))
    return aid


def list_assessments() -> pd.DataFrame:
    with get_conn() as c:
        df = pd.read_sql_query("""SELECT a.assessment_id, a.patient_id, p.age, p.gender, p.language, a.facility_type, a.assessed_at,
                                  a.urgency, a.review_status, a.reviewer FROM assessments a JOIN patients p USING(patient_id)""", c)
    if not df.empty:
        df["assessed_at"] = pd.to_datetime(df["assessed_at"])
        df["urgency_rank"] = df["urgency"].map(URGENCY_ORDER)
    return df


def get_case(aid: int):
    with get_conn() as c:
        a = c.execute("""SELECT a.*, p.age, p.gender, p.language, p.consent FROM assessments a
                         JOIN patients p USING(patient_id) WHERE a.assessment_id=?""", (aid,)).fetchone()
        if not a:
            return None
        case = dict(a)
        for k in ("urgency_reasons", "summary", "missing_info", "questions"):
            case[k] = json.loads(case[k]) if case[k] else None
        case["symptoms"] = [dict(r) for r in c.execute("SELECT symptom, duration, severity, negated FROM symptoms WHERE assessment_id=?", (aid,))]
        r = c.execute("SELECT * FROM reports WHERE assessment_id=?", (aid,)).fetchone()
        case["report"] = dict(r) if r else None
        if r and r["extracted_json"]:
            case["report"]["parsed"] = json.loads(r["extracted_json"])
        n = c.execute("SELECT * FROM triage_notes WHERE assessment_id=? ORDER BY note_id DESC LIMIT 1", (aid,)).fetchone()
        case["note"] = dict(n) if n else None
    return case


def update_review(aid: int, status: str, reviewer: str, comment: str):
    if status not in STATUSES:
        raise DatabaseError("Invalid review status.")
    with get_conn() as c:
        c.execute("UPDATE assessments SET review_status=?, reviewer=?, reviewed_at=?, reviewer_comment=? WHERE assessment_id=?",
                  (status, reviewer, _now(), comment, aid))


def save_note_edit(aid: int, text: str, editor: str):
    with get_conn() as c:
        c.execute("UPDATE triage_notes SET edited_note=?, edited_by=?, edited_at=? WHERE assessment_id=?", (text, editor, _now(), aid))


def add_log(aid, actor, role, action, details=""):
    with get_conn() as c:
        c.execute("INSERT INTO review_logs(assessment_id, actor, role, action, details, timestamp) VALUES (?,?,?,?,?,?)",
                  (aid, actor, role, action, details, _now()))


def get_logs(aid=None, limit=200):
    with get_conn() as c:
        q = "SELECT timestamp, actor, role, action, details, assessment_id FROM review_logs" + (" WHERE assessment_id=?" if aid else "")
        rows = c.execute(q + " ORDER BY log_id DESC LIMIT ?", ((aid, limit) if aid else (limit,))).fetchall()
    return [dict(r) for r in rows]


def list_users():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT username, display_name, role FROM users ORDER BY user_id")]


def get_stats():
    df = list_assessments()
    if df.empty:
        return {"total": 0, "pending": 0, "urgent": 0}
    return {"total": len(df), "pending": int((df.review_status == "Pending Review").sum()), "urgent": int((df.urgency == "URGENT REVIEW").sum())}
