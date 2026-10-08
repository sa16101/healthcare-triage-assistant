"""Multimodal Healthcare Triage Assistant - Streamlit entry point.  Run:  streamlit run app.py"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Healthcare Triage Assistant", page_icon="🩺", layout="wide")

from database import database as db  # noqa: E402
from modules.risk_engine import describe_rules  # noqa: E402
from modules.summarizer import llm_configured  # noqa: E402
from pages import patient_assessment, report_upload, reviewer_dashboard, case_review  # noqa: E402
from utils import audit_log, nav, privacy  # noqa: E402
from utils.ui import inject_css, DISCLAIMER  # noqa: E402

inject_css()


@st.cache_resource(show_spinner="Setting up demo database…")
def _setup():
    db.init_db()
    return True


try:
    _setup()
except Exception as e:  # noqa: BLE001
    st.error(f"The demo database could not be created: {e}")
    st.stop()


def home():
    st.markdown("# 🩺 Multimodal Healthcare Triage Assistant")
    st.markdown("##### AI-assisted information organization and triage support for healthcare professionals")
    st.warning(f"**Disclaimer:** {DISCLAIMER}", icon="⚠️")
    c = st.columns(3)
    if c[0].button("➕ Start New Assessment", type="primary", width="stretch"):
        st.switch_page(nav.REGISTRY["assess"])
    if c[1].button("📊 Reviewer Dashboard", width="stretch"):
        st.switch_page(nav.REGISTRY["dash"])
    if c[2].button("ℹ️ About System", width="stretch"):
        st.switch_page(nav.REGISTRY["about"])
    try:
        s = db.get_stats()
        m = st.columns(3)
        m[0].metric("Demo assessments", s["total"])
        m[1].metric("Pending reviews", s["pending"])
        m[2].metric("Urgent-review flags", s["urgent"])
    except db.DatabaseError as e:
        st.error(f"Could not read statistics: {e}")
    st.subheader("How it works")
    steps = ["Patient info + consent", "Symptoms (text / voice, EN / हिन्दी)", "Report upload + OCR", "Extraction & summary",
             "Missing info + follow-up questions", "Rule-based urgency flag", "Editable triage note", "Human review / escalation"]
    cols = st.columns(4)
    for i, s_ in enumerate(steps):
        cols[i % 4].markdown(f'<div class="card"><b>{i + 1}.</b> {s_}</div>', unsafe_allow_html=True)
    st.caption("Built for government hospitals, PHCs / CHCs, public health camps, company clinics, industrial health units and campus health centres.")


def about():
    st.header("ℹ️ About This System")
    st.warning(DISCLAIMER, icon="⚠️")
    with st.expander("Responsible AI & privacy", expanded=True):
        st.markdown("""
- **Synthetic data only**, minimal fields (pseudonymous ID, age, gender, language, facility), explicit consent checkbox.
- Free text is scanned for phone / email / Aadhaar-like patterns and redacted before analysis.
- **No diagnosis, prescription or treatment advice**: urgency is decided by transparent rules; LLM text passes a safety filter.
- AI output and the professional decision are stored and displayed separately; status values cannot express a diagnosis (DB constraint).
- Every important action is written to the audit log. Roles are a **mockup** (no real authentication).""")
    with st.expander("Urgency rule catalogue (illustrative thresholds - clinicians must validate)"):
        st.dataframe(pd.DataFrame(describe_rules()), hide_index=True, width="stretch")
    with st.expander("Role-based access (mockup)"):
        st.dataframe(pd.DataFrame([{"Role": r, "Permissions": ", ".join(privacy.PERM_LABELS[p] for p in sorted(ps))}
                                   for r, ps in privacy.ROLE_PERMISSIONS.items()]), hide_index=True, width="stretch")
    with st.expander("Limitations"):
        st.markdown("- Offline Hindi support is a small term dictionary (set `TRANSLATE_ONLINE=1` for online translation).\n"
                    "- OCR needs the Tesseract engine; voice needs internet.\n- Rules are simple and may miss or over-flag cases; a human must always review.")
    st.caption(f"LLM enhancement: {'enabled' if llm_configured() else 'not configured (rule-based mode)'}")


PAGES = {
    "home": st.Page(home, title="Home", icon="🏠", url_path="home", default=True),
    "assess": st.Page(patient_assessment.render, title="New Assessment", icon="🧾", url_path="assessment"),
    "report": st.Page(report_upload.render, title="Report OCR", icon="📄", url_path="report-ocr"),
    "dash": st.Page(reviewer_dashboard.render, title="Reviewer Dashboard", icon="📊", url_path="dashboard"),
    "review": st.Page(case_review.render, title="Case Review", icon="🗂️", url_path="case-review"),
    "about": st.Page(about, title="About System", icon="ℹ️", url_path="about"),
}
nav.REGISTRY.update(PAGES)

try:
    users = db.list_users()
    names = {u["username"]: u for u in users}
    with st.sidebar:
        st.divider()
        pick = st.selectbox("Demo role (access mockup)", list(names), index=list(names).index("dr_demo"),
                            format_func=lambda k: f"{names[k]['display_name']}", key="user_pick")
        st.session_state["user"] = names[pick]
        st.caption("Role: **" + names[pick]["role"] + "**")
        st.caption("🔒 Synthetic data only · Not for clinical use")
except db.DatabaseError as e:
    st.sidebar.error(f"Could not load users: {e}")

st.navigation(list(PAGES.values())).run()
