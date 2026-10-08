"""Shared Streamlit UI helpers: CSS, badges, and renderers reused by several pages."""
import html
import pandas as pd
import streamlit as st

DISCLAIMER = ("This is an educational prototype for triage-support purposes only. It does not provide medical diagnosis, "
              "treatment, or prescriptions. All information must be reviewed by a qualified healthcare professional.")
URG = {"URGENT REVIEW": ("#fde8e8", "#9b1c1c", "🔴"), "REVIEW REQUIRED": ("#fff4d6", "#8a5a00", "🟡"), "LOW PRIORITY": ("#e3f6ec", "#176b45", "🟢")}
STAT = {"Pending Review": ("#e8eefc", "#2a4a9b"), "Reviewed": ("#e3f6ec", "#176b45"), "More Info Requested": ("#f3e8fd", "#6b2a9b"),
        "Escalated": ("#fde8e8", "#9b1c1c")}


def inject_css():
    st.markdown("""<style>
    .block-container{padding-top:2rem;max-width:1250px}
    div[data-testid="stMetric"]{background:#fff;border:1px solid #e3e8ef;border-radius:12px;padding:14px 16px;box-shadow:0 1px 2px rgba(16,24,40,.05)}
    .badge{display:inline-block;padding:3px 12px;border-radius:999px;font-weight:600;font-size:.85rem;white-space:nowrap}
    .card{background:#fff;border:1px solid #e3e8ef;border-radius:14px;padding:16px 18px;margin-bottom:10px;box-shadow:0 1px 2px rgba(16,24,40,.05)}
    .flag{border-radius:14px;padding:16px 20px;margin:8px 0;border:1px solid}
    .ai-box{border-left:4px solid #6c7ae0;background:#f5f6ff;padding:10px 14px;border-radius:6px;margin:6px 0}
    .human-box{border-left:4px solid #1a9e6b;background:#f1fbf6;padding:10px 14px;border-radius:6px;margin:6px 0}
    </style>""", unsafe_allow_html=True)


def urgency_badge(cat):
    bg, fg, e = URG.get(cat, ("#eee", "#333", "⚪"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{e} {html.escape(str(cat))}</span>'


def status_badge(s):
    bg, fg = STAT.get(s, ("#eee", "#333"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{html.escape(str(s))}</span>'


def urgency_card(risk_or_cat, reasons=None, action=None):
    if isinstance(risk_or_cat, dict):
        cat, reasons, action = risk_or_cat["category"], risk_or_cat["reasons"], risk_or_cat["recommended_action"]
    else:
        cat = risk_or_cat
    bg, fg, e = URG[cat]
    st.markdown(f'<div class="flag" style="background:{bg};border-color:{fg}55"><div style="font-size:1.3rem;font-weight:700;color:{fg}">'
                f'{e} Urgency Category: {cat}</div></div>', unsafe_allow_html=True)
    st.markdown("**Reason:**")
    for r in reasons or []:
        st.markdown(f"- {r}")
    st.markdown(f"**Recommended Action:** {action}")
    st.info("**This is an urgency-support flag, not a medical diagnosis.**", icon="ℹ️")


def show_report_table(parsed):
    if not parsed or not parsed.get("tests"):
        st.caption("No test values could be parsed from the report text.")
        return
    df = pd.DataFrame(parsed["tests"])[["test", "value", "unit", "reference", "flag"]]
    df.columns = ["Test", "Reported value", "Unit", "Reference range", "Flag"]
    df["Flag"] = df["Flag"].map(lambda f: f"⚠️ {f}" if f in ("High", "Low", "Critical") else f)
    st.dataframe(df, hide_index=True, width="stretch")
    st.caption(f"Report date: {parsed.get('date') or 'not found'} · Values are shown as printed. No diagnosis is generated from the report.")


def show_summary(s):
    st.markdown(f'<div class="ai-box">🤖 <b>AI-generated summary</b> <i>({html.escape(s.get("narrative_source", "rule-based"))})</i><br>{html.escape(s["narrative"])}</div>',
                unsafe_allow_html=True)
    if s.get("llm_status"):
        st.caption(s["llm_status"])
    for title, key, kind in [("Patient Overview", "overview", "t"), ("Reported Symptoms", "reported_symptoms", "l"), ("Timeline", "timeline", "t"),
                             ("Uploaded Report Information", "report_info", "l"), ("Missing Information", "missing", "l"),
                             ("Relevant Observations", "observations", "l")]:
        with st.expander(title, expanded=key in ("reported_symptoms", "missing")):
            if kind == "t":
                st.write(s[key])
            else:
                for i in s[key] or ["None"]:
                    st.markdown(f"- {i}")


def show_questions(questions, language="English"):
    for i, q in enumerate(questions or [], 1):
        st.markdown(f"**{i}.** {q['en']}")
        if language == "Hindi" and q.get("hi"):
            st.markdown(f"<span style='color:#555;margin-left:1.4rem'>🇮🇳 {q['hi']}</span>", unsafe_allow_html=True)
        st.caption(f"↳ {q.get('reason', '')}")
