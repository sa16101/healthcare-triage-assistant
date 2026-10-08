"""New assessment workflow: patient info -> symptoms (text/voice) -> report -> analysis -> triage note -> save."""
import datetime as dt
import hashlib
import json
import random
import streamlit as st
from database import database as db
from modules.summarizer import llm_configured
from modules.translator import transcribe_audio
from modules.triage_note import analyze_case
from pages import report_upload
from utils import audit_log, privacy
from utils.ui import urgency_card, show_summary, show_questions, show_report_table

FACILITIES = ["Government Hospital", "Primary Health Centre (PHC)", "Community Health Centre (CHC)", "Public Health Camp",
              "Company Clinic", "Industrial Health Unit", "Campus Health Centre"]
SAMPLES = {"English": "Fever for 3 days\nCough\nBody pain\nWeakness", "Hindi": "मुझे तीन दिन से बुखार और खांसी है।\nबदन दर्द और कमजोरी भी है।"}
KEYS = ["p_id", "p_age", "p_gender", "p_lang", "p_facility", "p_date", "p_time", "p_consent", "symptom_text", "report_text", "report_name",
        "analysis", "note_edit", "saved_id", "save_error", "gen_errors", "voice_msg", "ocr_msg", "use_llm"]


def _defaults():
    ss = st.session_state
    ss.setdefault("p_id", f"DEMO{random.randint(100, 999)}")
    ss.setdefault("p_age", 35)
    ss.setdefault("p_gender", "Female")
    ss.setdefault("p_lang", "English")
    ss.setdefault("p_facility", FACILITIES[1])
    ss.setdefault("p_date", dt.date.today())
    ss.setdefault("p_time", dt.datetime.now().time().replace(second=0, microsecond=0))
    ss.setdefault("p_consent", False)
    ss.setdefault("symptom_text", "")
    ss.setdefault("report_text", "")


def _patient():
    ss = st.session_state
    return {"patient_id": (ss.get("p_id") or "").strip().upper(), "age": ss.get("p_age"), "gender": ss.get("p_gender"),
            "language": ss.get("p_lang"), "facility_type": ss.get("p_facility"), "consent": bool(ss.get("p_consent")),
            "assessed_at": dt.datetime.combine(ss["p_date"], ss["p_time"]).strftime("%Y-%m-%d %H:%M:%S")}


def _sig():
    ss = st.session_state
    return hashlib.md5(json.dumps([_patient(), ss.get("symptom_text"), ss.get("report_text"), bool(ss.get("use_llm"))], default=str).encode()).hexdigest()


def _load_sample(lang):
    st.session_state["symptom_text"] = SAMPLES[lang]


def _transcribe():
    audio = st.session_state.get("voice_audio")
    if audio is None:
        st.session_state["voice_msg"] = ("error", "Record something first, then press Transcribe.")
        return
    text, err = transcribe_audio(audio.getvalue(), st.session_state.get("p_lang", "English"))
    if err:
        st.session_state["voice_msg"] = ("error", err)
    else:
        cur = st.session_state.get("symptom_text", "")
        st.session_state["symptom_text"] = (cur + "\n" + text).strip()
        st.session_state["voice_msg"] = ("success", "Voice transcribed and added to the symptom box. Please check it.")


def _generate():
    ss = st.session_state
    ss["gen_errors"], ss["saved_id"] = [], None
    errs = privacy.validate_patient(_patient())
    if not (ss.get("symptom_text") or "").strip():
        errs.append("Symptom input is empty. Please type the symptoms (or use voice input) in step 2.")
    if errs:
        ss["gen_errors"] = errs
        return
    try:
        res = analyze_case(_patient(), ss["symptom_text"], ss.get("report_text", ""), ss.get("report_name", ""), use_llm=bool(ss.get("use_llm")))
    except Exception as e:  # noqa: BLE001
        ss["gen_errors"] = [f"Could not analyse the input ({e.__class__.__name__}). Please review the inputs and try again."]
        return
    res["_sig"] = _sig()
    ss["analysis"], ss["note_edit"] = res, res["note"]


def _save():
    ss, res, user = st.session_state, st.session_state.get("analysis"), privacy.current_user()
    ss["save_error"] = None
    if not res:
        return
    edited = ss.get("note_edit", "").strip() != res["note"].strip()
    try:
        aid = db.save_assessment(_patient(), res, edited_note=ss["note_edit"] if edited else None, editor=user["display_name"])
        audit_log.log_action(user, "assessment_submitted", f"AI urgency flag: {res['risk']['category']}", aid)
        if edited:
            audit_log.log_action(user, "note_edited_before_submit", "Triage note edited by staff", aid)
        ss["saved_id"] = aid
    except db.DatabaseError as e:
        ss["save_error"] = f"Could not save the assessment: {e}"


def _reset():
    for k in KEYS + ["report_file", "voice_audio"]:
        st.session_state.pop(k, None)


def render():
    st.header("🧾 New Assessment")
    if not privacy.has_perm("create"):
        st.error(f"Your current role ({privacy.current_user()['role']}) cannot create assessments. Switch the demo role in the sidebar.")
        return
    _defaults()
    st.info("Use **synthetic data only**. Do not enter names, phone numbers, Aadhaar or other personal identifiers.", icon="🔒")
    t1, t2, t3, t4 = st.tabs(["1 · Patient Information", "2 · Symptoms", "3 · Medical Report", "4 · Analysis & Triage Note"])

    with t1:
        a, b = st.columns(2)
        a.text_input("Patient ID (pseudonymous)", key="p_id", help="e.g. DEMO011")
        b.number_input("Age (years; 0 = under 1 year)", min_value=0, max_value=120, step=1, key="p_age")
        a.selectbox("Gender", privacy.GENDERS, key="p_gender")
        b.selectbox("Preferred language", privacy.LANGUAGES, key="p_lang")
        a.selectbox("Facility type", FACILITIES, key="p_facility")
        c1, c2 = b.columns(2)
        c1.date_input("Date", key="p_date")
        c2.time_input("Time", key="p_time")
        st.checkbox("Consent obtained: the patient agrees to record these details for triage support (synthetic demo).", key="p_consent")

    with t2:
        st.text_area("Describe the symptoms (English or हिन्दी)", key="symptom_text", height=170,
                     placeholder="Fever for 3 days\nCough\nBody pain\nWeakness")
        c1, c2, _ = st.columns([1, 1, 2])
        c1.button("Load English sample", on_click=_load_sample, args=("English",), width="stretch")
        c2.button("हिन्दी नमूना लोड करें", on_click=_load_sample, args=("Hindi",), width="stretch")
        with st.expander("🎙️ Optional voice input"):
            if hasattr(st, "audio_input"):
                st.audio_input("Record symptoms", key="voice_audio")
                st.button("Transcribe to text", on_click=_transcribe)
                st.caption("Uses the free Google Web Speech service via SpeechRecognition (internet needed). Voice is optional; typing always works.")
            else:
                st.warning("Voice recording needs Streamlit >= 1.40. Please type the symptoms.")
            if st.session_state.get("voice_msg"):
                getattr(st, st.session_state["voice_msg"][0])(st.session_state["voice_msg"][1])

    with t3:
        report_upload.render_report_input()

    with t4:
        c1, c2 = st.columns([2, 1])
        c1.checkbox("Use LLM for summary / extra questions (optional)", key="use_llm", disabled=not llm_configured(),
                    help="Set LLM_API_KEY to enable. Output is passed through a safety filter that blocks diagnostic wording.")
        c2.button("⚡ Generate Triage Assessment", on_click=_generate, type="primary", width="stretch")
        for e in st.session_state.get("gen_errors") or []:
            st.error(e)
        res = st.session_state.get("analysis")
        if res:
            if res.get("_sig") != _sig():
                st.warning("Inputs changed after the last analysis. Press **Generate Triage Assessment** again to refresh.")
            if res["pii_redacted"]:
                st.warning("Possible personal identifiers were removed from the symptom text: " + ", ".join(res["pii_redacted"]))
            urgency_card(res["risk"])
            x1, x2 = st.columns(2)
            with x1:
                st.subheader("Original & structured input")
                st.markdown("**Original patient input (unchanged)**")
                st.code(res["original_text"], language=None)
                st.caption(f"English working text · method: {res['translation_method']}")
                st.code(res["translated_text"], language=None)
                if res["untranslated"]:
                    st.caption("Terms not recognised by the offline dictionary: " + ", ".join(res["untranslated"]))
            with x2:
                st.subheader("Information summary")
                show_summary(res["summary"])
            if res["report"]:
                st.subheader("Uploaded report information")
                show_report_table(res["report"])
            st.subheader("Follow-up questions for the healthcare worker")
            show_questions(res["questions"], st.session_state.get("p_lang"))
            st.subheader("Triage note (editable)")
            st.text_area("Reviewer-facing note", key="note_edit", height=420, label_visibility="collapsed")
            if st.session_state.get("saved_id"):
                st.success(f"Submitted to the reviewer queue as case #{st.session_state['saved_id']}. Status: Pending Review.")
                st.button("➕ Start another assessment", on_click=_reset)
            else:
                st.button("📨 Submit to Reviewer Queue", on_click=_save, type="primary")
            if st.session_state.get("save_error"):
                st.error(st.session_state["save_error"])
        else:
            st.caption("Fill steps 1-3, then generate the assessment. Nothing is saved until you submit it to the reviewer queue.")
