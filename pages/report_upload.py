"""Medical report upload + OCR + information extraction (also reusable inside the assessment flow)."""
import datetime as dt
import re
from pathlib import Path
import streamlit as st
from modules.report_ocr import extract_text, parse_report, OCRError, SAMPLE_REPORT
from utils.ui import show_report_table

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"


def _run_ocr():
    f = st.session_state.get("report_file")
    st.session_state["ocr_msg"] = None
    if f is None:
        st.session_state["ocr_msg"] = ("error", "Please choose a PDF, JPG or PNG file first.")
        return
    try:
        data = f.getvalue()
        text, method = extract_text(data, f.name)
        try:  # keep a copy of the (synthetic) sample file for the demo
            UPLOAD_DIR.mkdir(exist_ok=True)
            (UPLOAD_DIR / f"{dt.datetime.now():%Y%m%d%H%M%S}_{re.sub(r'[^A-Za-z0-9._-]', '_', f.name)}").write_bytes(data)
        except OSError:
            pass
        st.session_state.update(report_text=text, report_name=f.name)
        st.session_state["ocr_msg"] = ("success", f"Text extracted using: {method}. Please check it and correct any OCR errors below.")
    except OCRError as e:
        st.session_state["ocr_msg"] = ("error", str(e))
    except Exception as e:  # noqa: BLE001
        st.session_state["ocr_msg"] = ("error", f"Unexpected problem while reading the file ({e.__class__.__name__}). You can paste the text manually.")


def _sample():
    st.session_state.update(report_text=SAMPLE_REPORT, report_name="sample_report_text.txt", ocr_msg=("success", "Synthetic sample report text loaded."))


def _clear():
    st.session_state.update(report_text="", report_name="", ocr_msg=None)


def render_report_input():
    st.caption("Optional. Upload a **synthetic / sample** report (no real patient records).")
    st.file_uploader("Upload report (PDF / JPG / PNG)", type=["pdf", "jpg", "jpeg", "png"], key="report_file")
    c1, c2, c3 = st.columns([1, 1, 1])
    c1.button("🔍 Run OCR", on_click=_run_ocr, type="primary", width="stretch")
    c2.button("📄 Use sample report text", on_click=_sample, width="stretch")
    c3.button("🧹 Clear report", on_click=_clear, width="stretch")
    msg = st.session_state.get("ocr_msg")
    if msg:
        getattr(st, msg[0])(msg[1])
    st.text_area("Extracted Report Text", key="report_text", height=200,
                 help="Editable: correct OCR mistakes here. If OCR is not available, paste the report text.")
    text = st.session_state.get("report_text", "")
    if text.strip():
        st.markdown("**Extracted values**")
        show_report_table(parse_report(text))


def render():
    st.header("📄 Report Upload & OCR")
    st.caption("Standalone OCR preview. In a real assessment, use the 'Medical Report' step of **New Assessment**.")
    st.session_state.setdefault("report_text", "")
    render_report_input()
