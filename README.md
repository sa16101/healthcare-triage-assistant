# 🩺 Multimodal Healthcare Triage Assistant

*AI-assisted information organization and triage support for healthcare professionals*

> **Disclaimer:** This is an educational prototype for triage-support purposes only. It does not provide medical diagnosis, treatment, or prescriptions. All information must be reviewed by a qualified healthcare professional. **Synthetic data only.**

## Project overview
A human-in-the-loop prototype for government hospitals, PHCs/CHCs, public health camps, company clinics, industrial health units and campus health centres in India. It collects symptoms (text / voice, English or Hindi) and sample reports (PDF / JPG / PNG with OCR), organises them into a structured triage note, lists missing information, generates follow-up questions and raises a **rule-based urgency flag** for a qualified reviewer. It never diagnoses, prescribes or recommends treatment.

## Features
- Patient form with consent checkbox, minimal data, ID validation, PII redaction in free text
- Symptom extraction: symptoms, duration, severity, negation ("no fever"), temperature, vitals, conditions, medicines, progression
- English + Hindi input (Devanagari or romanised); original text always kept visible; follow-up questions shown in Hindi too
- Report OCR (Tesseract, PDF text layer, editable text) → test / value / unit / reference range / date / flagged values
- Information summary, missing-information list, follow-up questions
- Transparent urgency rules (🟢 LOW PRIORITY · 🟡 REVIEW REQUIRED · 🔴 URGENT REVIEW) with rule IDs and reasons
- Editable triage note; reviewer dashboard (KPIs, filters, Plotly charts); case review with *Mark Reviewed / Request More Information / Escalate*
- Audit log, role-based access mockup, DB constraint so AI can never set a "diagnosed" status
- Optional LLM summary / extra questions behind a safety filter

## Technology stack
Python · Streamlit · SQLite · Pandas · Plotly · pytesseract / pdfplumber / pdf2image · SpeechRecognition · deep-translator (optional) · OpenAI-compatible LLM API (optional)

## Installation & run
```bash
pip install -r requirements.txt
streamlit run app.py
```
The SQLite DB (`database/triage_demo.db`) is created and seeded with 12 synthetic cases automatically on first run.

### Requirements
- Python 3.10+
- **Tesseract OCR** for image/scanned-PDF OCR (`sudo apt install tesseract-ocr tesseract-ocr-hin` / Windows installer from UB-Mannheim). Without it the app still works: use *sample report text* or paste text.
- **poppler** only for OCR of scanned PDFs (PDFs with a text layer work without it)
- Internet only for voice-to-text (Google Web Speech) and optional online translation / LLM

### Environment variables (all optional)
| Variable | Purpose |
|---|---|
| `LLM_API_KEY` | Enables LLM summary / extra questions (any OpenAI-compatible API) |
| `LLM_BASE_URL` | Default `https://api.openai.com/v1` (use your provider / local server URL) |
| `LLM_MODEL` | Default `gpt-4o-mini` |
| `TRANSLATE_ONLINE=1` | Use online Hindi→English translation (offline dictionary is the default and fallback) |
| `TRIAGE_DB_PATH` | Custom SQLite file location |

Missing keys never crash the app: it falls back to the rule-based summary.

## Database setup
Automatic. Tables: `users, patients, assessments, symptoms, reports, triage_notes, review_logs` (see `database/schema.sql`). To reset the demo, delete `database/triage_demo.db` and restart.

## Sample usage
1. **New Assessment** → tab 1: tick consent → tab 2: click *Load Hindi sample* (or type / record voice) → tab 3: *Use sample report text* or upload `data/sample_reports/sample_cbc_report.png` and *Run OCR* → tab 4: *Generate Triage Assessment* → edit note → *Submit to Reviewer Queue*.
2. **Reviewer Dashboard** → filter, select a row → *Open in Case Review*.
3. **Case Review** → read AI-prepared info, edit note, then *Mark Reviewed / Request More Information / Escalate* (switch demo role in the sidebar to see role limits).

## Project structure
```
healthcare_triage_assistant/
├── app.py                 # entry point, navigation, home/about, role switcher
├── requirements.txt  README.md
├── database/   database.py  schema.sql
├── modules/    symptom_processor  report_ocr  summarizer  risk_engine
│               question_generator  translator  triage_note
├── pages/      patient_assessment  report_upload  reviewer_dashboard  case_review
├── data/       sample_patients.csv  sample_reports/
├── uploads/    (copies of uploaded sample reports)
└── utils/      privacy.py  audit_log.py  ui.py  nav.py
```
`app.py` uses `st.navigation`, so the `pages/` folder is imported as normal modules (not auto-listed by Streamlit).

## Privacy considerations
Synthetic data only; consent required; pseudonymous patient ID; no name/phone/address fields; phone, email and Aadhaar-like patterns are redacted from free text; only redacted facts go to an LLM; every key action is audit-logged; roles are a mockup (add real authentication, encryption at rest, and data-protection review (e.g. DPDP Act 2023) before any real use).

## Responsible AI limitations
- Urgency thresholds are **illustrative** and must be validated by clinicians before any pilot.
- Rules can miss or over-flag; "LOW PRIORITY" never means "no risk".
- The offline Hindi dictionary is small; unknown terms are listed so staff can verify.
- OCR and parsing can be wrong; the extracted text is editable and must be checked.
- LLM output is optional, filtered for diagnostic / treatment wording, and never replaces the rule-based flag.
- Not a medical device; not for clinical use.

## Disclaimer
This is an educational prototype for triage-support purposes only. It does not provide medical diagnosis, treatment, or prescriptions. All information must be reviewed by a qualified healthcare professional.
