"""Follow-up questions for the healthcare worker (English + Hindi). Questions gather information; they never diagnose."""
import json
import re
from modules.summarizer import SAFETY_FILTER, call_llm

Q = {
    "temperature": ("What was the highest recorded temperature, and how was it measured?", "सबसे अधिक दर्ज किया गया तापमान कितना था, और उसे कैसे मापा गया?"),
    "duration": ("When did the symptoms begin?", "लक्षण कब शुरू हुए?"),
    "conditions": ("Are there any existing medical conditions (e.g. diabetes, high blood pressure, asthma)?", "क्या कोई पहले से मौजूद बीमारी है (जैसे डायबिटीज़, उच्च रक्तचाप, अस्थमा)?"),
    "medications": ("Is the patient currently taking any medication (including for these symptoms)?", "क्या मरीज़ अभी कोई दवा ले रहा है (इन लक्षणों के लिए भी)?"),
    "progression": ("Are the symptoms getting better, staying the same, or getting worse?", "क्या लक्षण बेहतर हो रहे हैं, वैसे ही हैं, या बिगड़ रहे हैं?"),
    "severity": ("How severe are the symptoms (mild / moderate / severe)? Do they limit daily activities?", "लक्षण कितने गंभीर हैं (हल्के / मध्यम / गंभीर)? क्या ये रोज़मर्रा के काम में बाधा डालते हैं?"),
    "additional": ("Are there any other symptoms, such as breathing difficulty, chest pain, vomiting, rash or dizziness?", "क्या कोई अन्य लक्षण हैं, जैसे सांस लेने में तकलीफ़, सीने में दर्द, उल्टी, चकत्ते या चक्कर?"),
    "vitals": ("Can vital signs (BP, pulse, SpO2, respiratory rate) be measured and recorded?", "क्या महत्वपूर्ण संकेत (बीपी, नाड़ी, SpO2, सांस की दर) मापकर दर्ज किए जा सकते हैं?"),
    "pregnancy": ("Is there any possibility of pregnancy?", "क्या गर्भावस्था की कोई संभावना है?"),
}
BY_SYMPTOM = {
    "cough": ("Is the cough dry or with phlegm? Is there any blood in the phlegm?", "खांसी सूखी है या बलगम के साथ? क्या बलगम में खून आता है?"),
    "fever": ("Any chills, rash, recent travel, or similar illness at home / in the neighbourhood?", "क्या ठंड लगना, चकत्ते, हाल की यात्रा, या घर/आसपास किसी को ऐसी ही बीमारी हुई है?"),
    "vomiting": ("How many episodes per day, and can the patient keep fluids down? Is urine output reduced?", "दिन में कितनी बार उल्टी हो रही है, और क्या मरीज़ तरल पदार्थ पी पा रहा है? क्या पेशाब कम हुआ है?"),
    "diarrhoea": ("How many loose stools per day, and can the patient keep fluids down? Is urine output reduced?", "दिन में कितनी बार दस्त हो रहे हैं, और क्या मरीज़ तरल पदार्थ पी पा रहा है? क्या पेशाब कम हुआ है?"),
    "chest pain": ("When did the chest discomfort start, and is it present at rest?", "सीने की तकलीफ़ कब शुरू हुई, और क्या यह आराम करते समय भी रहती है?"),
    "breathlessness": ("When did the breathing difficulty start, and is it present at rest?", "सांस की दिक्कत कब शुरू हुई, और क्या यह आराम करते समय भी रहती है?"),
    "headache": ("Any vision changes, neck stiffness, or recent head injury?", "क्या नज़र में बदलाव, गर्दन में अकड़न, या हाल में सिर पर चोट लगी है?"),
    "abdominal pain": ("Where exactly is the pain, and is it constant or on-and-off?", "दर्द ठीक किस जगह है, और क्या यह लगातार है या रुक-रुक कर?"),
    "burning urination": ("Is the burning urination accompanied by fever, back pain or blood in urine?", "क्या पेशाब की जलन के साथ बुखार, कमर दर्द या पेशाब में खून है?"),
    "injury / localized pain": ("How and when did the injury happen? Any swelling, deformity or difficulty moving the area?", "चोट कैसे और कब लगी? क्या सूजन, विकृति या हिलने-डुलने में कठिनाई है?"),
    "bleeding": ("Where is the bleeding from, how long has it lasted, and roughly how much?", "खून कहाँ से आ रहा है, कितने समय से, और लगभग कितना?"),
}
CHILD_Q = ("Is the child drinking / feeding normally and active?", "क्या बच्चा सामान्य रूप से पी / खा रहा है और सक्रिय है?")


def generate_questions(patient: dict, ex: dict, missing: list, use_llm: bool = False, limit: int = 10) -> list:
    out = [{"en": Q[m["key"]][0], "hi": Q[m["key"]][1], "reason": f"Missing: {m['label']}"} for m in missing if m["key"] in Q]
    for s in ex["symptoms"]:
        if not s["negated"] and s["name"] in BY_SYMPTOM:
            en, hi = BY_SYMPTOM[s["name"]]
            out.append({"en": en, "hi": hi, "reason": f"Reported: {s['name']}"})
    if patient.get("age") is not None and patient["age"] <= 5:
        out.append({"en": CHILD_Q[0], "hi": CHILD_Q[1], "reason": "Young child"})
    out = out[:limit]
    if use_llm:
        txt, _ = call_llm("Suggest up to 3 additional neutral clarifying questions a nurse could ask to complete a triage note. "
                          "Questions only: no diagnosis, no treatment advice. Return a JSON array of strings.",
                          json.dumps({"symptoms": [s["name"] for s in ex["symptoms"] if not s["negated"]], "already_asked": [q["en"] for q in out]}))
        try:
            for q in json.loads(re.sub(r"```(?:json)?", "", txt or "[]").strip())[:3]:
                if isinstance(q, str) and q.strip().endswith("?") and not SAFETY_FILTER.search(q):
                    out.append({"en": q.strip(), "hi": None, "reason": "LLM-suggested"})
        except Exception:  # noqa: BLE001
            pass
    return out
