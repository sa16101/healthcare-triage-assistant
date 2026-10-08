"""English/Hindi support: offline term normalisation, optional online translation, speech-to-text."""
import io
import os
import re
import unicodedata

_nfc = lambda s: unicodedata.normalize("NFC", s)
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

_PHRASES = {
    "सीने में दर्द": "chest pain", "सीने में दबाव": "chest pain", "सीने में जकड़न": "chest tightness",
    "सांस लेने में तकलीफ": "difficulty breathing", "साँस लेने में तकलीफ": "difficulty breathing",
    "सांस फूलना": "breathlessness", "साँस फूलना": "breathlessness", "सांस फूल": "breathlessness",
    "सिर में दर्द": "headache", "सिरदर्द": "headache", "सिर दर्द": "headache", "सर दर्द": "headache",
    "पेट में दर्द": "abdominal pain", "पेट दर्द": "abdominal pain",
    "गले में दर्द": "sore throat", "गले में खराश": "sore throat",
    "बदन दर्द": "body pain", "शरीर में दर्द": "body pain", "शरीर दर्द": "body pain",
    "जोड़ों में दर्द": "joint pain", "पेशाब में जलन": "burning urination",
    "भूख नहीं लगती": "loss of appetite", "भूख कम": "loss of appetite",
    "दूध कम पी रहा": "poor feeding", "दूध नहीं पी रहा": "poor feeding",
    "नाक बह रही": "runny nose", "नाक बह": "runny nose",
    "खून आ रहा": "bleeding", "खून बह रहा": "bleeding", "खून की उल्टी": "vomiting blood",
    "बेहोशी": "loss of consciousness", "बेहोश": "loss of consciousness",
    "दौरे": "seizure", "दौरा": "seizure", "चक्कर": "dizziness", "उल्टी": "vomiting",
    "पतले दस्त": "diarrhoea", "दस्त": "diarrhoea", "बुखार": "fever", "खांसी": "cough", "खाँसी": "cough",
    "जुकाम": "runny nose", "सर्दी": "cold", "कमजोरी": "weakness", "कमज़ोरी": "weakness",
    "थकान": "fatigue", "धड़कन": "palpitations", "सूजन": "swelling", "चकत्ते": "rash", "खुजली": "itching",
    "चोट": "injury", "डायबिटीज़": "diabetes", "डायबिटीज": "diabetes", "मधुमेह": "diabetes",
    "उच्च रक्तचाप": "hypertension", "ब्लड प्रेशर": "blood pressure", "अस्थमा": "asthma", "दमा": "asthma",
    "गर्भवती": "pregnant", "दवा": "medicine", "गोली": "tablet",
    "आज सुबह से": "since this morning", "कल रात से": "since last night", "कल से": "since yesterday",
    "बढ़ रहा": "worsening", "बढ़ रही": "worsening", "बढ़ गया": "worsening", "ठीक हो रहा": "improving",
}
PHRASES = sorted(((_nfc(k), v) for k, v in _PHRASES.items()), key=lambda kv: -len(kv[0]))
TOKENS = {_nfc(k): v for k, v in {
    "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", "पाँच": "5", "छह": "6", "छः": "6", "सात": "7",
    "आठ": "8", "नौ": "9", "दस": "10", "पंद्रह": "15", "बीस": "20",
    "दिन": "days", "दिनों": "days", "हफ्ते": "weeks", "हफ्ता": "weeks", "सप्ताह": "weeks", "घंटे": "hours",
    "महीने": "months", "महीना": "months", "साल": "years", "डिग्री": "degrees",
    "और": "and", "नहीं": "no", "तेज": "severe", "तेज़": "severe", "हल्का": "mild", "हल्की": "mild",
    "लगातार": "persistent", "बच्चे": "child", "बच्ची": "child", "बच्चा": "child", "बहुत": "",
}.items()}
STOP = {_nfc(w) for w in ["मुझे", "मुझको", "मेरे", "मेरा", "मेरी", "है", "हैं", "हूँ", "हूं", "था", "थी", "से", "का",
                          "की", "के", "को", "में", "रही", "रहा", "रहे", "हो", "भी", "ने", "पर", "पिछले", "तो"]}
ROMAN = {r"\bbukhar\b": "fever", r"\bkhansi\b": "cough", r"\bsardi\b": "cold", r"\bsir ?dard\b": "headache",
         r"\bpet (?:me|mein) dard\b": "abdominal pain", r"\bulti\b": "vomiting", r"\bdast\b": "diarrhoea",
         r"\bkamzori\b": "weakness", r"\bchakkar\b": "dizziness", r"\bbadan dard\b": "body pain",
         r"\bsaans (?:phoolna|phool)\b": "breathlessness", r"\bseene (?:me|mein) dard\b": "chest pain",
         r"\bdin\b": "days", r"\bhafte\b": "weeks"}


def is_hindi(text: str) -> bool:
    return bool(DEVANAGARI.search(text or ""))


def _offline(text: str):
    t = _nfc(text).translate(_DIGITS).replace("।", ".")
    for k, v in PHRASES:
        t = t.replace(k, f"⟦{v}⟧")
    t = re.sub(r"⟦([^⟧]+)⟧\s*(?:भी\s*)?नहीं(?:\s+(?:है|हैं|हो|होता|होती))?", r"no \1", t)
    t = t.replace("⟦", "").replace("⟧", "")
    out, left = [], []
    for tok in re.findall(r"[\u0900-\u097F]+|[^\u0900-\u097F\s]+|\s+", t):
        if DEVANAGARI.search(tok):
            if tok in TOKENS:
                out.append(TOKENS[tok])
            elif tok in STOP:
                out.append("")
            else:
                out.append(tok)
                left.append(tok)
        else:
            out.append(tok)
    return re.sub(r"[ \t]+", " ", "".join(out)).strip(), left


def translate_to_english(text: str):
    """Returns (english_text, method, untranslated_tokens). Original text is never modified by callers."""
    text = text or ""
    if os.getenv("TRANSLATE_ONLINE", "0") == "1" and is_hindi(text):
        try:
            from deep_translator import GoogleTranslator
            out = GoogleTranslator(source="auto", target="en").translate(text)
            if out:
                return out, "online translation (deep-translator)", []
        except Exception:
            pass  # fall back to offline dictionary
    if is_hindi(text):
        eng, left = _offline(text)
        return eng, "offline Hindi term dictionary", left
    low, changed = text, False
    for pat, rep in ROMAN.items():
        new = re.sub(pat, rep, low, flags=re.I)
        changed = changed or new != low
        low = new
    return low, ("romanised-Hindi terms normalised" if changed else "none (English input)"), []


def transcribe_audio(audio_bytes: bytes, language: str = "English"):
    """Returns (text, error_message). Needs SpeechRecognition + internet (Google Web Speech)."""
    try:
        import speech_recognition as sr
    except ImportError:
        return None, "Speech-to-text package not installed (pip install SpeechRecognition). Please type the symptoms instead."
    try:
        rec = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio_bytes)) as src:
            audio = rec.record(src)
        return rec.recognize_google(audio, language="hi-IN" if language == "Hindi" else "en-IN"), None
    except sr.UnknownValueError:
        return None, "Could not understand the audio. Please speak clearly or type the symptoms."
    except sr.RequestError:
        return None, "Speech service unreachable (internet needed for voice input). Please type the symptoms."
    except Exception as e:  # noqa: BLE001
        return None, f"Audio could not be processed ({e.__class__.__name__}). Please type the symptoms."
