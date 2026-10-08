"""Audit trail for important actions (stored in review_logs). Logging failures never break the app."""
from database import database as db


def log_action(user: dict, action: str, details: str = "", assessment_id=None) -> bool:
    try:
        db.add_log(assessment_id, user.get("display_name", "system"), user.get("role", "system"), action, details)
        return True
    except Exception:  # noqa: BLE001
        return False


def get_logs(assessment_id=None, limit=200):
    try:
        return db.get_logs(assessment_id, limit)
    except Exception:  # noqa: BLE001
        return []
