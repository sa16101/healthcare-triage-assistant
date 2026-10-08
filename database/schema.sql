CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('Health Worker','Nurse','Medical Officer','Auditor'))
);
CREATE TABLE IF NOT EXISTS patients (
  patient_id TEXT PRIMARY KEY,
  age INTEGER CHECK (age BETWEEN 0 AND 120),
  gender TEXT,
  language TEXT,
  consent INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS assessments (
  assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id TEXT NOT NULL REFERENCES patients(patient_id),
  facility_type TEXT,
  assessed_at TEXT NOT NULL,
  original_text TEXT,
  translated_text TEXT,
  translation_method TEXT,
  urgency TEXT NOT NULL CHECK (urgency IN ('LOW PRIORITY','REVIEW REQUIRED','URGENT REVIEW')),
  urgency_reasons TEXT,
  summary TEXT,
  missing_info TEXT,
  questions TEXT,
  -- AI can never set a "diagnosed" status: only these human workflow states exist
  review_status TEXT NOT NULL DEFAULT 'Pending Review'
    CHECK (review_status IN ('Pending Review','Reviewed','More Info Requested','Escalated')),
  reviewer TEXT,
  reviewed_at TEXT,
  reviewer_comment TEXT
);
CREATE TABLE IF NOT EXISTS symptoms (
  symptom_id INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_id INTEGER NOT NULL REFERENCES assessments(assessment_id),
  symptom TEXT NOT NULL,
  duration TEXT,
  severity TEXT,
  negated INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reports (
  report_id INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_id INTEGER NOT NULL REFERENCES assessments(assessment_id),
  filename TEXT,
  ocr_text TEXT,
  extracted_json TEXT,
  flagged_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS triage_notes (
  note_id INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_id INTEGER NOT NULL REFERENCES assessments(assessment_id),
  ai_note TEXT NOT NULL,
  edited_note TEXT,
  edited_by TEXT,
  edited_at TEXT
);
CREATE TABLE IF NOT EXISTS review_logs (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_id INTEGER,
  actor TEXT,
  role TEXT,
  action TEXT NOT NULL,
  details TEXT,
  timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assess_urgency ON assessments(urgency, review_status);
