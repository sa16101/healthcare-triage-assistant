"""Reviewer dashboard: KPIs, filters, Plotly charts and the recent-cases queue."""
import pandas as pd
import plotly.express as px
import streamlit as st
from database import database as db
from utils import nav, privacy

COLORS = {"URGENT REVIEW": "#d64545", "REVIEW REQUIRED": "#f0ad2c", "LOW PRIORITY": "#2e9e6b"}
EMOJI = {"URGENT REVIEW": "🔴", "REVIEW REQUIRED": "🟡", "LOW PRIORITY": "🟢"}
ORDER = list(COLORS)


def _style(fig, h=320):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def render():
    st.header("📊 Reviewer Dashboard")
    if not privacy.has_perm("view_dashboard"):
        st.error("Your role cannot view the dashboard.")
        return
    try:
        df = db.list_assessments()
    except db.DatabaseError as e:
        st.error(f"Could not load cases. {e}")
        return
    if df.empty:
        st.info("No assessments yet. Create one from **New Assessment**.")
        return
    with st.expander("🔎 Filters", expanded=True):
        c = st.columns(5)
        lo, hi = df.assessed_at.min().date(), df.assessed_at.max().date()
        rng = c[0].date_input("Date range", value=(lo, hi), min_value=lo, max_value=hi)
        fac = c[1].multiselect("Facility", sorted(df.facility_type.unique()), default=[])
        urg = c[2].multiselect("Urgency", ORDER, default=[])
        lang = c[3].multiselect("Language", sorted(df.language.unique()), default=[])
        stat = c[4].multiselect("Review status", db.STATUSES, default=[])
    f = df.copy()
    if isinstance(rng, (tuple, list)) and len(rng) == 2:
        f = f[(f.assessed_at.dt.date >= rng[0]) & (f.assessed_at.dt.date <= rng[1])]
    for col, sel in (("facility_type", fac), ("urgency", urg), ("language", lang), ("review_status", stat)):
        if sel:
            f = f[f[col].isin(sel)]
    k = st.columns(5)
    k[0].metric("Total assessments", len(f))
    k[1].metric("Pending reviews", int((f.review_status == "Pending Review").sum()))
    k[2].metric("🟢 Low priority", int((f.urgency == "LOW PRIORITY").sum()))
    k[3].metric("🟡 Review required", int((f.urgency == "REVIEW REQUIRED").sum()))
    k[4].metric("🔴 Urgent review", int((f.urgency == "URGENT REVIEW").sum()))
    if f.empty:
        st.warning("No cases match the selected filters.")
        return
    r1 = st.columns(2)
    fig = px.pie(f, names="urgency", hole=.55, color="urgency", color_discrete_map=COLORS, category_orders={"urgency": ORDER}, title="Cases by urgency flag")
    r1[0].plotly_chart(_style(fig), width="stretch")
    daily = f.assign(date=f.assessed_at.dt.date).groupby(["date", "urgency"]).size().reset_index(name="cases")
    fig = px.bar(daily, x="date", y="cases", color="urgency", color_discrete_map=COLORS, category_orders={"urgency": ORDER}, title="Assessments per day")
    r1[1].plotly_chart(_style(fig), width="stretch")
    r2 = st.columns(2)
    fac_df = f.groupby(["facility_type", "urgency"]).size().reset_index(name="cases")
    fig = px.bar(fac_df, y="facility_type", x="cases", color="urgency", orientation="h", color_discrete_map=COLORS, title="Cases by facility type")
    r2[0].plotly_chart(_style(fig), width="stretch")
    st_df = f.groupby(["review_status", "language"]).size().reset_index(name="cases")
    fig = px.bar(st_df, x="review_status", y="cases", color="language", barmode="group", title="Review status by patient language",
                 category_orders={"review_status": db.STATUSES})
    r2[1].plotly_chart(_style(fig), width="stretch")

    st.subheader("Recent cases (urgent first)")
    q = f.sort_values(["urgency_rank", "assessed_at"], ascending=[True, False]).reset_index(drop=True)
    view = pd.DataFrame({"Case #": q.assessment_id, "Patient ID": q.patient_id, "Age": q.age, "Gender": q.gender, "Language": q.language,
                         "Facility": q.facility_type, "Assessed": q.assessed_at.dt.strftime("%d %b %H:%M"),
                         "Urgency flag": q.urgency.map(lambda u: f"{EMOJI[u]} {u}"), "Status": q.review_status})
    ev = st.dataframe(view, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="case_table")
    rows = ev.selection.rows if ev and ev.selection else []
    if rows:
        cid = int(view.iloc[rows[0]]["Case #"])
        if st.button(f"📂 Open case #{cid} in Case Review", type="primary"):
            st.session_state["selected_case"] = cid
            st.switch_page(nav.REGISTRY["review"])
    else:
        st.caption("Select a row to open it in Case Review.")
