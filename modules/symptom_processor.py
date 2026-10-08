"""Rule-based extraction of symptoms, duration, severity, vitals and observations from (English) text.
Pure pattern matching: no diagnosis is inferred."""
import re

SYMPTOMS = {
    "fever": r"\bfever(?:ish)?\b|\bhigh temperature\b|\bpyrexia\b",
    "cough": r"\bcough(?:ing)?\b",
    "cold / runny nose": r"\brunny nose\b|\bcold\b|\bsneezing\b|\bnasal congestion\b|\bblocked nose\b",
    "sore throat": r"\bsore throat\b|\bthroat pain\b",
    "body pain": r"\bbody\s*(?:pain|ache)s?\b|\bmyalgia\b",
    "joint pain": r"\bjoint\s*pains?\b|\barthralgia\b",
    "headache": r"\bheadache\b|\bhead pain\b",
    "weakness": r"\bweakness\b|\bweak\b",
    "fatigue": r"\bfatigue\b|\btired(?:ness)?\b",
    "chest pain": r"\bchest (?:pain|tightness|pressure|discomfort)\b",
    "breathlessness": r"\bbreathless(?:ness)?\b|\bshort(?:ness)? of breath\b|\bdifficulty (?:in )?breathing\b|\bunable to breathe\b|\bwheez(?:e|ing)\b",
    "abdominal pain": r"\b(?:abdominal|stomach|belly) pain\b|\bpain in (?:the )?(?:abdomen|stomach)\b|\bstomach ache\b",
    "vomiting": r"\bvomit(?:ing|s)?\b|\bnausea\b",
    "diarrhoea": r"\bdiarr?h?oea\b|\bdiarrhea\b|\bloose (?:stools?|motions?)\b",
    "dizziness": r"\bdizz(?:y|iness)\b|\bgiddiness\b|\blightheaded(?:ness)?\b",
    "palpitations": r"\bpalpitations?\b|\brapid heart ?beat\b",
    "rash / itching": r"\brash(?:es)?\b|\bitching\b|\bitchy\b",
    "swelling": r"\bswelling\b|\bswollen\b",
    "burning urination": r"\bburning (?:urination|micturition|while urinating)\b|\bpainful urination\b",
    "loss of appetite": r"\bloss of appetite\b|\bno appetite\b",
    "poor feeding / drinking": r"\bpoor feeding\b|\breduced feeding\b|\bnot feeding\b|\bnot drinking\b|\bunable to drink\b",
    "bleeding": r"\bbleeding\b|\bblood in (?:stool|urine|vomit|sputum)\b|\bvomiting blood\b|\bcoughing (?:up )?blood\b",
    "injury / localized pain": r"\binjur(?:y|ed)\b|\bfracture\b|\bfall(?:en)? from\b|\bpain in (?:the )?(?:left |right )?(?:leg|arm|back|knee|shoulder|hand|foot|neck)\b|\b(?:back|neck|knee|leg|arm|shoulder) pain\b",
    "loss of consciousness": r"\bunconscious\w*\b|\bfaint(?:ed|ing)\b|\bblack(?:ed)? out\b|\bloss of consciousness\b|\bunresponsive\b",
    "seizure": r"\bseizures?\b|\bconvulsions?\b|\bfits\b",
    "confusion": r"\bconfus(?:ed|ion)\b|\bdisorient\w+\b",
    "slurred speech / facial droop": r"\bslurred speech\b|\bfacial droop\b|\bface drooping\b|\bone[- ]sided weakness\b",
    "self-harm statement": r"\bsuicid\w*\b|\bself[- ]harm\b|\bwant to die\b",
}
_SYM_RE = {k: re.compile(v) for k, v in SYMPTOMS.items()}

CONDITIONS = {
    "diabetes": r"\bdiabet\w*\b",
    "hypertension": r"\bhypertension\b|\bhypertensive\b|\bhigh blood pressure\b",
    "asthma / chronic lung disease": r"\basthma\b|\bcopd\b|\bchronic lung\b",
    "heart disease": r"\bheart (?:disease|problem|condition|failure|attack)\b|\bcardiac\b",
    "kidney disease": r"\bkidney (?:disease|failure|problem)\b|\bckd\b|\bdialysis\b",
    "tuberculosis": r"\btb\b|\btuberculosis\b",
    "cancer": r"\bcancer\b|\bchemotherapy\b",
    "pregnancy": r"\bpregnan\w*\b",
}
_COND_RE = {k: re.compile(v) for k, v in CONDITIONS.items()}
MEDS_RE = re.compile(r"\b(?:paracetamol|ibuprofen|aspirin|antibiotics?|insulin|inhaler|metformin|amlodipine|tablets?|medicines?|medications?|syrup)\b")
NO_COND_RE = re.compile(r"\bno (?:known |significant |major )?(?:medical |chronic )?(?:conditions?|illness\w*|comorbidit\w+|problems?|history|diseases?)\b")

_NUMW = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}
_UNIT_DAYS = {"hour": 1 / 24, "hr": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}
DUR_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?|" + "|".join(_NUMW) + r")\s*-?\s*(hours?|hrs?|days?|weeks?|months?|years?)\b(?!\s*-?\s*old)")
REL_RE = re.compile(r"\b(since yesterday|since this morning|since morning|since last night|since last week|since today|from yesterday)\b")
REL_DAYS = {"since yesterday": 1, "from yesterday": 1, "since this morning": 0.5, "since morning": 0.5,
            "since last night": 0.5, "since last week": 7, "since today": 0.5}
SEV_WORDS = [("severe", r"severe|unbearable|intense|excruciating|extreme|worst|serious"),
             ("moderate", r"moderate"), ("mild", r"mild|slight|little")]


def _neg(pre: str) -> bool:
    pre = re.split(r"[,;.]|\bbut\b", pre)[-1]
    return bool(re.search(r"\b(?:no|not|without|denies|denied|denying|nil|never|negative for|absence of|absent)\b", pre))


def _duration(unit: str):
    m = DUR_RE.search(unit)
    if m:
        n = _NUMW.get(m.group(1)) or float(m.group(1))
        u = m.group(2).rstrip("s")
        u = "hour" if u in ("hr",) else u
        return f"{n:g} {u}{'' if n == 1 else 's'}", n * _UNIT_DAYS["hour" if u == "hour" else u]
    m = REL_RE.search(unit)
    if m:
        return m.group(1), REL_DAYS[m.group(1)]
    return None


def _units(text: str):
    out = []
    for clause in re.split(r"[\n;]+|\.(?=\s|$)", text):
        clause = clause.strip()
        if not clause:
            continue
        parts = [p for p in clause.split(",") if p.strip()]
        if len(parts) > 1 and sum(bool(_duration(p)) for p in parts) >= 2:
            out.extend(p.strip() for p in parts)
        else:
            out.append(clause)
    return out


def _severity(unit: str, start: int, single: bool):
    win = re.split(r",|\band\b|\bwith\b", unit[max(0, start - 30):start])[-1]
    best = None
    for lvl, pat in SEV_WORDS:
        for m in re.finditer(rf"\b(?:{pat})\b", win):
            if best is None or m.start() > best[0]:
                best = (m.start(), lvl)
    if best:
        return best[1]
    if re.search(r"\b(?:very|high)\s*$", win):
        return "severe"
    if single:
        for lvl, pat in SEV_WORDS:
            if re.search(rf"\b(?:{pat})\b", unit):
                return lvl
        m = re.search(r"(\d{1,2})\s*/\s*10\b", unit)
        if m:
            v = int(m.group(1))
            return "severe" if v >= 7 else "moderate" if v >= 4 else "mild"
    return None


def _temperature(text: str):
    cands = []
    for rx in (r"(\d{2,3}(?:\.\d)?)\s*(?:°|º|degrees?|deg)\s*([fc])?\b",
               r"(?<![\d./])(\d{2,3}(?:\.\d)?)\s*(?:°|º)?\s*([fc])\b",
               r"\bfever\D{0,12}?(\d{2,3}(?:\.\d)?)(?![\d/]|\s*(?:days?|hours?|weeks?|%))()"):
        for m in re.finditer(rx, text):
            v, u = float(m.group(1)), (m.group(2) or "")
            u = u or ("f" if v >= 60 else "c")
            f = v if u == "f" else v * 9 / 5 + 32
            if (u == "f" and 94 <= v <= 110) or (u == "c" and 34 <= v <= 43.5):
                cands.append(round(f, 1))
    return max(cands) if cands else None


def extract(text: str) -> dict:
    text = (text or "").lower()
    symptoms, durations = {}, []
    for unit in _units(text):
        dur = _duration(unit)
        if dur:
            durations.append(dur)
        hits = []
        for name, rx in _SYM_RE.items():
            m = rx.search(unit)
            if m:
                hits.append((m.start(), name))
        single = len(hits) == 1
        for start, name in hits:
            neg, sev = _neg(unit[:start]), _severity(unit, start, single)
            rec = symptoms.get(name)
            if rec is None:
                symptoms[name] = {"name": name, "duration": dur[0] if dur else None,
                                  "duration_days": dur[1] if dur else None, "severity": sev, "negated": neg}
            else:
                if rec["negated"] and not neg:
                    rec["negated"] = False
                if not rec["duration"] and dur:
                    rec["duration"], rec["duration_days"] = dur
                rec["severity"] = rec["severity"] or sev
    overall = max(durations, key=lambda d: d[1]) if durations else None

    conditions = [n for n, rx in _COND_RE.items()
                  if any(not _neg(text[:m.start()]) for m in rx.finditer(text))]
    meds_hits = [m for m in MEDS_RE.finditer(text)]
    meds = sorted({m.group(0) for m in meds_hits if not _neg(text[:m.start()])})
    meds_denied = any(_neg(text[:m.start()]) for m in meds_hits)

    prog = None
    if re.search(r"\bnot (?:getting )?(?:better|improving)\b", text):
        prog = "not improving"
    elif re.search(r"\bworsen\w*|\bgetting worse\b|\bincreasing\b|\baggravat\w*|\bdeteriorat\w*", text):
        prog = "worsening"
    elif re.search(r"\bimprov\w*|\bgetting better\b|\breducing\b|\bdecreasing\b", text):
        prog = "improving"

    vit = {}
    m = re.search(r"\bspo2\s*[:=]?\s*(\d{2,3})", text) or re.search(r"\boxygen(?: saturation)?\s*[:=]?\s*(\d{2,3})\s*%", text)
    if m:
        vit["spo2"] = int(m.group(1))
    m = re.search(r"\b(?:bp|blood pressure)\s*[:=]?\s*(\d{2,3})\s*/\s*(\d{2,3})", text)
    if m:
        vit["sbp"], vit["dbp"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"\b(?:pulse|heart rate)\s*[:=]?\s*(\d{2,3})", text)
    if m:
        vit["pulse"] = int(m.group(1))

    temp_f = _temperature(text)
    obs = []
    if temp_f:
        obs.append(f"Recorded temperature mentioned: {temp_f:g} °F ({(temp_f - 32) * 5 / 9:.1f} °C)")
    if prog:
        obs.append(f"Progression mentioned: {prog}")
    if conditions:
        obs.append("Existing conditions mentioned: " + ", ".join(conditions))
    if meds:
        obs.append("Medication mentioned: " + ", ".join(meds))
    if vit:
        obs.append("Vitals mentioned: " + ", ".join(f"{k.upper()} {v}" for k, v in vit.items()))
    denied = [s["name"] for s in symptoms.values() if s["negated"]]
    if denied:
        obs.append("Patient denies / reports absence of: " + ", ".join(denied))
    return {"symptoms": list(symptoms.values()), "overall_duration": overall, "temp_f": temp_f,
            "conditions": conditions, "conditions_denied": bool(NO_COND_RE.search(text)),
            "medications": meds, "meds_denied": meds_denied, "progression": prog, "vitals": vit,
            "observations": obs}


def present(ex: dict):
    return [s["name"] for s in ex["symptoms"] if not s["negated"]]
