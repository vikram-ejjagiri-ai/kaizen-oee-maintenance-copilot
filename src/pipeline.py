"""Run everything: simulate -> check -> OEE -> knowledge base -> evaluate -> report.

    python -m src.pipeline            # uses Ollama if it is running
    python -m src.pipeline --no-llm   # fallback mode only (fast, no Ollama needed)
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime

import pandas as pd

from src import checks, config, copilot, evaluate, oee, plotting, simulate
from src.retrieval import OllamaEmbedder, Retriever, build_chunks, model_available, ollama_models


def build_system(use_llm: bool = True, verbose: bool = False):
    """Load data, run checks, build retriever and copilot. Used by the app too."""
    if not (config.DATA_DIR / "events.csv").exists():
        simulate.save(simulate.simulate())
    tables, check_results = checks.run_checks(simulate.load())
    facts = oee.shift_facts(tables)
    models = ollama_models() if use_llm else None
    embedder = OllamaEmbedder() if model_available(config.EMBED_MODEL, models) else None
    if verbose:
        print(f"Ollama: {'running, models: ' + ', '.join(models) if models else 'not running'}")
    retriever = Retriever(build_chunks(tables["work_orders"]), embedder)
    bot = copilot.Copilot(tables, facts, retriever, use_llm=use_llm)
    return tables, check_results, facts, retriever, bot


def pct(x: float) -> str:
    return f"{100 * x:.1f} %"


def main(use_llm: bool = True) -> None:
    print("1/6 Simulating 13 weeks of MES data ...")
    simulate.save(simulate.simulate())

    print("2/6 Data checks, OEE engine, knowledge base ...")
    tables, check_results, facts, retriever, bot = build_system(use_llm, verbose=True)
    (config.DATA_DIR / "processed").mkdir(exist_ok=True)
    facts.to_csv(config.DATA_DIR / "processed" / "shift_facts.csv", index=False)
    print(f"    {len(retriever.chunks)} knowledge chunks | retrieval: "
          f"{'hybrid (BM25 + ' + config.EMBED_MODEL + ')' if retriever.has_dense else 'BM25 only'} | "
          f"copilot: {bot.mode}")

    print("3/6 Figures ...")
    plotting.oee_by_week(facts)
    plotting.loss_waterfall(facts)
    plotting.downtime_pareto(tables)
    plotting.cnc02_story(tables, facts)
    whole = copilot.Period(facts.shift_date.min().date(), facts.shift_date.max().date(), "all")
    press_setup = copilot.setup_by_shift(tables, whole, ["PRESS-01"])
    plotting.press_setup_by_shift(press_setup)

    print("4/6 Retrieval evaluation ...")
    questions = evaluate.load_questions()
    ret = evaluate.retrieval_eval(retriever, questions)
    ret_sum = evaluate.retrieval_summary(ret)
    ret_cat = ret.pivot_table(index="category", columns="method", values="hit@3", aggfunc="mean", sort=False)

    print(f"5/6 End-to-end evaluation ({len(questions)} questions, {bot.mode}) ...")
    e2e = evaluate.end_to_end_eval(bot, questions)
    e2e_sum = evaluate.end_to_end_summary(e2e)
    config.REPORTS_DIR.mkdir(exist_ok=True)
    e2e.to_csv(config.REPORTS_DIR / "eval_answers.csv", index=False)

    print("6/6 Writing report ...")
    md, summary = report(tables, check_results, facts, press_setup, ret_sum, ret_cat, e2e, e2e_sum, retriever, bot)
    (config.REPORTS_DIR / "results.md").write_text(md, encoding="utf-8")
    (config.REPORTS_DIR / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    update_readme(md)
    if retriever.dense_failures:
        print(f"NOTE: {retriever.dense_failures} searches fell back to BM25 because Ollama embeddings failed.")
    print(f"\nDone. Plant OEE {summary['plant_oee']}, end-to-end pass rate {summary['e2e_pass_rate']}.")
    print("Report: reports/results.md   App: streamlit run app/app.py")


def report(tables, check_results, facts, press_setup, ret_sum, ret_cat, e2e, e2e_sum, retriever, bot):
    ret_n = int((e2e.id.str.startswith("R")).sum())
    plant = oee.aggregate(facts).iloc[0]
    bym = oee.aggregate(facts, ["machine_id"]).sort_values("oee")
    par = oee.downtime_pareto(tables)
    setup_share = par.loc[par.reason_code == "SETUP", "share"].sum()
    ps = press_setup.set_index("shift").avg_min
    cnc = oee.aggregate(facts[facts.machine_id == "CNC-02"], ["week"]).set_index("week").oee
    before = oee.aggregate(facts[(facts.machine_id == "CNC-02") & (facts.shift_date < "2026-07-06")]).oee.iloc[0]
    wo = tables["work_orders"]
    lc = tables["events"][(tables["events"].reason_code == "SENSOR_LC")]
    lc_before = lc[lc.shift_date < "2026-08-12"].shape[0] / max(1, facts[(facts.machine_id == "ASSY-01") & (facts.shift_date < "2026-08-12")].shape[0])
    lc_after = lc[lc.shift_date >= "2026-08-13"].shape[0] / max(1, facts[(facts.machine_id == "ASSY-01") & (facts.shift_date >= "2026-08-13")].shape[0])
    ht = tables["events"][(tables["events"].reason_code == "HYD_TEMP")]
    ht_min_before = ht[(ht.shift_date >= "2026-07-06") & (ht.shift_date < "2026-07-24")].duration_min.sum()

    n_ret = int((~e2e.category.isin(["safety", "out_of_scope", "kpi"])).sum())
    lines = [
        f"*Generated {datetime.now():%Y-%m-%d %H:%M} by `python -m src.pipeline`. Copilot mode: {bot.mode}. "
        f"Retrieval: {'hybrid BM25 + dense (' + config.EMBED_MODEL + ')' if retriever.has_dense else 'BM25 with plant glossary (Ollama not running)'}.*",
        "",
        "### Plant performance (13 weeks, 4 machines, 3 shifts)",
        f"Plant OEE **{pct(plant.oee)}** (availability {pct(plant.availability)}, performance "
        f"{pct(plant.performance)}, quality {pct(plant.quality)}).",
        "",
        "| Machine | OEE | Availability | Performance | Quality |",
        "|---|---|---|---|---|",
        *[f"| {r.machine_id} | {pct(r.oee)} | {pct(r.availability)} | {pct(r.performance)} | {pct(r.quality)} |"
          for r in bym.itertuples()],
        "",
        "### What the data shows",
        f"1. **Changeovers are the biggest single downtime reason** ({setup_share * 100:.0f} % of unplanned stop time).",
        f"2. **PRESS-01 die changes take {ps['Night']:.0f} min on the night shift vs. {ps['Early']:.0f} min early "
        f"and {ps['Late']:.0f} min late** (target 35 min): a SMED / night-shift support topic, not a machine fault.",
        f"3. **CNC-02 announced its failure.** OEE fell from {pct(before)} (June) to {pct(cnc['2026-W31'])} in "
        f"week 31. A-217 vibration warnings rose for three weeks, a technician noted elevated vibration on "
        f"16 July, but no bearing inspection was planned; the bearing failed on 30 July (about 17 h downtime).",
        f"4. **ASSY-01 light curtain (S-310):** {lc_before:.2f} stops per shift until the damaged receiver cable "
        f"was found on 12 August, {lc_after:.2f} afterwards. The earlier lens cleaning only helped for ten days.",
        f"5. **PRESS-01 oil over-temperature (H-104):** {ht_min_before:,} min of stops in the July heat wave "
        f"before the oil cooler was cleaned and its fan replaced on 24 July.",
        "",
        "### Data checks",
        "| Check | Status | Detail |",
        "|---|---|---|",
        *[f"| {r.check} | {r.status} | {r.detail} |" for r in check_results],
        "",
        "### Copilot evaluation",
        f"**Retrieval** ({ret_n} questions with a known correct source, top 5 results, "
        "searched in the same lanes as the copilot: documents or work orders):",
        "",
        "| Method | Hit@1 | Hit@3 | MRR |",
        "|---|---|---|---|",
        *[f"| {r.method} | {pct(r._2)} | {pct(r._3)} | {r.mrr:.3f} |" for r in ret_sum.itertuples()],
        "",
        "Hit@3 by question type:",
        "",
        "| Type | " + " | ".join(ret_cat.columns) + " |",
        "|---|" + "---|" * len(ret_cat.columns),
        *[f"| {idx} | " + " | ".join(pct(v) for v in row) + " |" for idx, row in ret_cat.iterrows()],
        "",
        f"**End to end** ({len(e2e)} questions: right sources, safety refusals, out-of-scope handling, "
        "KPI numbers checked against an independent calculation):",
        "",
        "| Question type | Questions | Passed |",
        "|---|---|---|",
        *[f"| {r.category} | {r.questions} | {r.passed} ({pct(r.pass_rate)}) |" for r in e2e_sum.itertuples()],
        f"| **total** | **{len(e2e)}** | **{int(e2e.passed.sum())} ({pct(e2e.passed.mean())})** |",
        "",
    ]
    if "llm_citations" in e2e:
        llm = e2e.dropna(subset=["llm_citations"])
        lines += [f"LLM answers ({len(llm)}): citations present in {pct(llm.llm_citations.astype(bool).mean())}, "
                  f"all numbers traceable to the facts in {pct(llm.llm_numbers_verified.astype(bool).mean())}, "
                  f"median latency {llm.latency_s.median():.1f} s.", ""]
    failed = e2e[~e2e.passed]
    if len(failed):
        lines += ["Failed questions (kept visible on purpose):", ""]
        lines += [f"- {r.id} ({r.category}): {r.question} -> {r.detail}" for r in failed.itertuples()]
        lines.append("")
    summary = {
        "plant_oee": pct(plant.oee),
        "machines": {r.machine_id: pct(r.oee) for r in bym.itertuples()},
        "press_setup_avg_min": {k: round(float(v), 1) for k, v in ps.items()},
        "retrieval": ret_sum.round(3).to_dict(orient="records"),
        "e2e_pass_rate": pct(e2e.passed.mean()),
        "e2e_by_category": e2e_sum.round(3).to_dict(orient="records"),
        "copilot_mode": bot.mode,
        "dense_retrieval": retriever.has_dense,
        "work_orders": int(len(wo)),
    }
    return "\n".join(lines), summary


def update_readme(md: str) -> None:
    path = config.ROOT / "README.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    new = re.sub(r"<!-- RESULTS:START -->.*<!-- RESULTS:END -->",
                 lambda _: f"<!-- RESULTS:START -->\n{md}\n<!-- RESULTS:END -->", text, flags=re.S)
    path.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="do not use Ollama")
    main(use_llm=not ap.parse_args().no_llm)
