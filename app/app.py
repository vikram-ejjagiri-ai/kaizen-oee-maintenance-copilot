"""Kaizen OEE dashboard + maintenance copilot.

    streamlit run app/app.py
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # must be set before numpy/pandas load

import sys  # noqa: E402
from datetime import timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import checks, oee  # noqa: E402
from src.pipeline import build_system  # noqa: E402
from src.plotting import MACHINE_COLORS  # noqa: E402

st.set_page_config(page_title="Kaizen OEE + Maintenance Copilot", page_icon="🏭", layout="wide")


@st.cache_resource(show_spinner="Loading plant data and knowledge base ...")
def system(use_llm: bool):
    return build_system(use_llm)


def pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{100 * x:.1f} %"


use_llm = st.sidebar.toggle("Use local LLM (Ollama)", value=True,
                            help="Off = fallback mode: facts and passages without an LLM.")
tables, check_results, facts, retriever, bot = system(use_llm)

st.sidebar.title("Filters")
dmin, dmax = facts.shift_date.min().date(), facts.shift_date.max().date()
dates = st.sidebar.date_input("Period", (dmin, dmax), min_value=dmin, max_value=dmax)
start, end = (dates if isinstance(dates, tuple) and len(dates) == 2 else (dmin, dmax))
machines = st.sidebar.multiselect("Machines", list(MACHINE_COLORS), default=list(MACHINE_COLORS))
shifts = st.sidebar.multiselect("Shifts", ["Early", "Late", "Night"], default=["Early", "Late", "Night"])
st.sidebar.caption("Simulated plant data (fictional machines). Production Mon-Fri, 3 shifts.")

tab_dash, tab_bot, tab_dq = st.tabs(["📊 OEE dashboard", "🛠️ Maintenance copilot", "✅ Data quality"])

# --------------------------------------------------------------------------------------
def dashboard():
    f = oee.filter_facts(facts, start, end, machines, shifts)
    if f.empty:
        st.warning("No data for this selection.")
        return
    tot = oee.aggregate(f).iloc[0]
    length = (end - start).days + 1
    prev = oee.filter_facts(facts, start - timedelta(days=length), start - timedelta(days=1), machines, shifts)
    p = oee.aggregate(prev).iloc[0] if not prev.empty else None

    def delta(col):
        if p is None or pd.isna(p[col]):
            return None
        return f"{100 * (tot[col] - p[col]):+.1f} pts vs previous {length} days"

    c = st.columns(5)
    c[0].metric("OEE", pct(tot.oee), delta("oee"))
    c[1].metric("Availability", pct(tot.availability), delta("availability"))
    c[2].metric("Performance", pct(tot.performance), delta("performance"))
    c[3].metric("Quality", pct(tot.quality), delta("quality"))
    c[4].metric("Good parts", f"{int(tot.good_count):,}", f"{int(tot.scrap_count):,} scrap", delta_color="off")

    left, right = st.columns(2)
    with left:
        w = oee.aggregate(f, ["week", "machine_id"])
        fig = px.line(w, x="week", y=w.oee * 100, color="machine_id", markers=True,
                      color_discrete_map=MACHINE_COLORS, labels={"y": "OEE %", "week": "", "machine_id": "Machine"},
                      title="OEE by week", category_orders={"machine_id": list(MACHINE_COLORS)})
        fig.update_xaxes(tickvals=sorted(w.week.unique()), ticktext=[x[-3:] for x in sorted(w.week.unique())])
        fig.update_traces(line_width=2, hovertemplate="%{x}<br>OEE %{y:.1f} %")
        st.plotly_chart(fig, width="stretch")
    with right:
        wf = oee.loss_waterfall(f)
        fig = go.Figure(go.Waterfall(
            x=wf.step, y=wf.minutes / 60, measure=["absolute"] + ["relative"] * 5 + ["total"],
            text=[f"{abs(m) / wf.minutes.iloc[0] * 100:.1f} %" for m in wf.minutes], textposition="outside",
            decreasing={"marker": {"color": "#e34948"}}, totals={"marker": {"color": "#2a78d6"}},
            increasing={"marker": {"color": "#2a78d6"}}, connector={"line": {"color": "#c3c2b7"}}))
        fig.update_layout(title="Where planned production time goes (hours)", showlegend=False,
                          yaxis_range=[wf.minutes.iloc[0] / 60 * 0.55, wf.minutes.iloc[0] / 60 * 1.06])
        st.plotly_chart(fig, width="stretch")
        st.caption("Y-axis starts at 55 % so the losses are visible.")

    left, right = st.columns(2)
    with left:
        par = oee.downtime_pareto(tables, start, end, machines, shifts).head(10).iloc[::-1]
        fig = px.bar(par, x=par.minutes / 60, y="description", orientation="h", title="Downtime Pareto (hours)",
                     labels={"x": "hours", "description": ""}, hover_data={"stops": True, "reason_code": True})
        fig.update_traces(marker_color="#2a78d6")
        st.plotly_chart(fig, width="stretch")
    with right:
        hm = oee.aggregate(f, ["machine_id", "shift"]).pivot(index="machine_id", columns="shift", values="oee")
        hm = hm.reindex(columns=[s for s in ["Early", "Late", "Night"] if s in hm.columns])
        fig = px.imshow(hm * 100, text_auto=".1f", color_continuous_scale="Blues", aspect="auto",
                        labels={"color": "OEE %", "x": "", "y": ""}, title="OEE by machine and shift")
        st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Reliability")
        rel = oee.reliability(tables, facts, start, end)
        rel = rel[rel.machine_id.isin(machines)]
        st.dataframe(rel.rename(columns={"mtbf_h": "MTBF (run h)", "mttr_min": "MTTR (min)"}).round(1),
                     hide_index=True, width="stretch")
    with right:
        st.subheader("Latest work orders")
        wo = tables["work_orders"]
        wo = wo[wo.machine_id.isin(machines) & (wo.created_ts.dt.date >= start) & (wo.created_ts.dt.date <= end)]
        st.dataframe(wo.sort_values("created_ts", ascending=False)[
            ["wo_id", "machine_id", "type", "priority", "symptom", "cause", "downtime_min"]].head(15),
            hide_index=True, width="stretch")


with tab_dash:
    dashboard()

# --------------------------------------------------------------------------------------
with tab_bot:
    st.caption(f"Mode: **{bot.mode}** · Retrieval: **{'hybrid (BM25 + embeddings)' if retriever.has_dense else 'BM25 + plant glossary'}** · "
               "Numbers come from the OEE engine, never from the LLM. Sources are cited.")
    examples = ["Why was OEE low on CNC-02 at the end of July?",
                "Which shift has the longest die changes on the press?",
                "What fixed the light curtain fault on ASSY-01 last time?",
                "The press keeps overheating, what should I check?",
                "What does alarm A-217 mean?"]
    if "chat" not in st.session_state:
        st.session_state.chat = []
    cols = st.columns(len(examples))
    clicked = None
    for col, ex in zip(cols, examples):
        if col.button(ex, width="stretch"):
            clicked = ex
    question = st.chat_input("Ask about OEE, downtime, alarms, procedures or past repairs ...") or clicked
    if question:
        with st.spinner("Thinking ..."):
            st.session_state.chat.append(bot.ask(question))

    for a in reversed(st.session_state.chat):
        with st.chat_message("user"):
            st.write(a.question)
        with st.chat_message("assistant"):
            st.markdown(a.text)
            for flag in a.flags:
                if flag not in ("safety_refusal", "not_found"):
                    st.warning(f"Check: {flag}")
            if a.sources:
                with st.expander(f"Sources ({len(a.sources)})"):
                    for i, (c, _) in enumerate(a.sources, 1):
                        st.markdown(f"**[S{i}] {c.citation()}** · _{c.source_type}_")
                        st.caption(c.text[:800])
            if a.kpi and a.kpi["tables"]:
                with st.expander("KPI tables"):
                    for name, tbl in a.kpi["tables"].items():
                        st.markdown(f"**{name}**")
                        st.dataframe(tbl.round(3), hide_index=True, width="stretch")

# --------------------------------------------------------------------------------------
with tab_dq:
    st.subheader("Data checks")
    st.dataframe(checks.results_frame(check_results), hide_index=True, width="stretch")
    st.subheader("Raw tables")
    name = st.selectbox("Table", ["events", "counts", "alarms", "work_orders", "machines", "products", "reason_codes"])
    st.dataframe(tables[name].head(500), hide_index=True, width="stretch")
