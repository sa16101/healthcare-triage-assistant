"""OCR + parsing of lab-style reports. Extracts what is printed; never interprets it clinically."""
import io
import re

SUPPORTED = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_MB = 10
SAMPLE_REPORT = """CITY GOVT HOSPITAL LABORATORY (SYNTHETIC SAMPLE)
Date: 02/10/2026
Test Name  Result  Unit  Reference Range
Hemoglobin 9.1 g/dL 12.0 - 15.5 L
Total WBC Count 11800 /cumm 4000 - 11000 H
Platelet Count 210000 /cumm 150000 - 410000
Serum Creatinine 0.8 mg/dL 0.6 - 1.1
Fasting Blood Sugar 98 mg/dL 70 - 100"""


class OCRError(Exception):
    """Raised with a user-friendly message."""


def extract_text(data: bytes, filename: str):
    """Returns (text, method). Raises OCRError with friendly text."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED:
        raise OCRError(f"Unsupported file type '{ext or 'unknown'}'. Please upload PDF, JPG or PNG.")
    if len(data) > MAX_MB * 1024 * 1024:
        raise OCRError(f"File is larger than {MAX_MB} MB. Please upload a smaller sample report.")
    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join((p.extract_text() or "") for p in pdf.pages).strip()
            if len(text) > 20:
                return text, "PDF text layer"
        except ImportError:
            pass
        except Exception as e:  # noqa: BLE001
            raise OCRError(f"The PDF could not be read ({e.__class__.__name__}). It may be corrupted or password-protected.")
        try:
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(data, dpi=200, first_page=1, last_page=3)
        except Exception:  # noqa: BLE001
            raise OCRError("This PDF has no text layer and image conversion is unavailable (needs poppler). Paste the report text manually.")
    else:
        try:
            from PIL import Image
            images = [Image.open(io.BytesIO(data))]
        except Exception:  # noqa: BLE001
            raise OCRError("The image could not be opened. Please upload a valid JPG or PNG.")
    try:
        import pytesseract
    except ImportError:
        raise OCRError("OCR package not installed (pip install pytesseract) – or paste the report text manually.")
    try:
        parts = []
        for im in images:
            try:
                parts.append(pytesseract.image_to_string(im, lang="eng+hin"))
            except pytesseract.TesseractError:
                parts.append(pytesseract.image_to_string(im))  # Hindi language pack missing
        text = "\n".join(parts).strip()
    except pytesseract.TesseractNotFoundError:
        raise OCRError("Tesseract OCR engine is not installed on this machine. Install it, or paste the report text manually / use the sample text.")
    except Exception as e:  # noqa: BLE001
        raise OCRError(f"OCR failed ({e.__class__.__name__}). Please paste the report text manually.")
    if len(text) < 10:
        raise OCRError("OCR found no readable text. Try a clearer image or paste the report text manually.")
    return text, "Tesseract OCR"


_LINE = re.compile(r"^\s*(?P<name>[A-Za-z][A-Za-z0-9 \(\)/%\-\.,]{1,45}?)\s*[:|]?\s+(?P<value>\d+(?:\.\d+)?)\s*(?P<rest>.*)$")
_REF = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)")
_SKIP = re.compile(r"\b(date|age|patient|phone|ref(?:erence)? no|page|sample|lab no|reg|collected|reported|mobile|id)\b", re.I)
_DATE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b")


def parse_report(text: str) -> dict:
    tests, date = [], None
    for line in (text or "").splitlines():
        if date is None and re.search(r"date|collected|reported", line, re.I):
            m = _DATE.search(line)
            date = m.group(1) if m else None
        m = _LINE.match(line)
        if not m or _SKIP.search(m.group("name")):
            continue
        value, rest = float(m.group("value")), m.group("rest")
        um = re.match(r"\s*(%|[A-Za-zµμ/\^][A-Za-z0-9µμ/\^\.\*]*)", rest)
        unit = um.group(1) if um else ""
        rm = _REF.search(rest)
        lo, hi = (float(rm.group(1)), float(rm.group(2))) if rm else (None, None)
        fm = re.search(r"(?:\s|^)(H|L|HIGH|LOW|High|Low|CRITICAL|Critical)\s*\*?\s*$", rest.strip()) or None
        flag = None
        if fm:
            flag = "Low" if fm.group(1).upper().startswith("L") else "High" if fm.group(1).upper().startswith("H") else "Critical"
        elif lo is not None:
            flag = "Low" if value < lo else "High" if value > hi else None
        tests.append({"test": m.group("name").strip(" .:-"), "value": value, "unit": unit,
                      "reference": f"{lo:g} - {hi:g}" if lo is not None else "", "flag": flag or "Normal / not flagged",
                      "abnormal": flag is not None})
    return {"date": date, "tests": tests, "abnormal_count": sum(t["abnormal"] for t in tests)}
