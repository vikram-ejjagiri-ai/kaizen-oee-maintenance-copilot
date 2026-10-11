"""Evaluate the copilot like a product, not a demo.

1. Retrieval: does the right manual section / work order come back? (Hit@1, Hit@3, MRR)
   compared for bm25_raw, bm25 (+ glossary), dense and hybrid (dense needs Ollama).
2. End to end: does the copilot answer with the right sources, refuse unsafe requests,
   say "not found" for off-topic questions, and report KPI numbers that match an
   independent calculation?
3. LLM answers (only if Ollama runs): citations present, no numbers that are not in the facts.
"""
from __future__ import annotations

import json
import re
import time

import pandas as pd

from src import config
from src.copilot import Copilot, parse
from src.retrieval import Chunk, Retriever


def load_questions() -> list[dict]:
    with open(config.EVAL_DIR / "questions.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def matches(chunk: Chunk, rule: dict) -> bool:
    if "chunk" in rule:
        return chunk.chunk_id == rule["chunk"]
    return (chunk.source_type == "work_order" and rule["wo_machine"] in chunk.machines
            and rule["wo_contains"].lower() in chunk.text.lower())


def first_hit_rank(chunks: list[Chunk], expected: list[dict]) -> int | None:
    for rank, c in enumerate(chunks, 1):
        if any(matches(c, r) for r in expected):
            return rank
    return None


def retrieval_eval(retriever: Retriever, questions: list[dict], k: int = 5) -> pd.DataFrame:
    methods = ["bm25_raw", "bm25"] + (["dense", "hybrid"] if retriever.has_dense else [])
    rows = []
    for q in (q for q in questions if "expected" in q):
        machines = parse(q["question"]).machines
        machine = machines[0] if len(machines) == 1 else None
        # same "lanes" as the copilot: work orders and documents are searched separately
        types = {"work_order"} if "wo_machine" in q["expected"][0] else {"manual", "sop"}
        for m in methods:
            hits = [c for c, _ in retriever.search(q["question"], k=k, method=m, machine=machine,
                                                   types=types)]
            rank = first_hit_rank(hits, q["expected"])
            rows.append({"id": q["id"], "category": q["category"], "method": m, "rank": rank,
                         "hit@1": rank == 1, "hit@3": rank is not None and rank <= 3,
                         "rr": 1 / rank if rank else 0.0})
    return pd.DataFrame(rows)


def retrieval_summary(df: pd.DataFrame) -> pd.DataFrame:
    s = df.groupby("method", sort=False)[["hit@1", "hit@3", "rr"]].mean().rename(columns={"rr": "mrr"})
    return s.reset_index()


# --------------------------------------------------------------------------------------
# Independent KPI check: a deliberately different, simple calculation from the raw tables
# --------------------------------------------------------------------------------------
def independent_kpis(t: dict, machines: list[str], start: str, end: str) -> dict:
    ev, cnt, prod = t["events"], t["counts"], t["products"]
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    ev = ev[(ev.shift_date >= s) & (ev.shift_date <= e)]
    cnt = cnt[(cnt.shift_date >= s) & (cnt.shift_date <= e)]
    if machines:
        ev, cnt = ev[ev.machine_id.isin(machines)], cnt[cnt.machine_id.isin(machines)]
    ppt = ev.loc[ev.state != "PLANNED_STOP", "duration_min"].sum()
    run = ev.loc[ev.state == "RUNNING", "duration_min"].sum()
    c = cnt.merge(prod, on=["machine_id", "product_id"])
    good_time = (c.good_count * c.ideal_cycle_s).sum() / 60
    scrap = (c.scrap_startup + c.scrap_process).sum()
    return {"oee": good_time / ppt, "availability": run / ppt, "scrap_rate": scrap / c.total_count.sum()}


def _read_pct(lines: list[str], name: str) -> float | None:
    for line in lines:
        m = re.search(rf"\b{name}\b \(?([\d.]+) %", line, re.I)
        if m:
            return float(m.group(1)) / 100
    return None


def end_to_end_eval(copilot: Copilot, questions: list[dict]) -> pd.DataFrame:
    rows = []
    for q in questions:
        t0 = time.perf_counter()
        a = copilot.ask(q["question"])
        row = {"id": q["id"], "category": q["category"], "question": q["question"], "mode": a.mode,
               "latency_s": time.perf_counter() - t0, "flags": "; ".join(a.flags), "passed": False,
               "detail": ""}
        if "expected" in q:
            hit = first_hit_rank([c for c, _ in a.sources], q["expected"])
            row["passed"] = hit is not None
            row["detail"] = f"expected source at position {hit}" if hit else "expected source missing"
        elif "expect_mode" in q:
            row["passed"] = a.mode == q["expect_mode"]
            row["detail"] = f"mode = {a.mode}"
        elif "expected_kpi" in q:
            k = q["expected_kpi"]
            truth = independent_kpis(copilot.t, k["machines"], k["start"], k["end"])
            lines = a.kpi["lines"] if a.kpi else []
            got = {"oee": _read_pct(lines, "OEE"), "availability": _read_pct(lines, "availability"),
                   "scrap_rate": None}
            sm = re.search(r"scrap [\d,]+ \(([\d.]+) %\)", " ".join(lines))
            got["scrap_rate"] = float(sm.group(1)) / 100 if sm else None
            period_ok = bool(a.kpi) and str(a.kpi["period"].start) == k["start"] and str(a.kpi["period"].end) == k["end"]
            ok = all(got[m] is not None and abs(got[m] - truth[m]) < 0.0006 for m in truth)
            row["passed"] = period_ok and ok
            row["detail"] = (f"period {'OK' if period_ok else 'WRONG'}; OEE copilot {got['oee']} vs "
                             f"independent {truth['oee']:.4f}")
        if a.mode.startswith("LLM"):
            row["llm_citations"] = "no_citations" not in a.flags
            row["llm_numbers_verified"] = not any(f.startswith("unverified_numbers") for f in a.flags)
        row["answer"] = a.text
        rows.append(row)
    return pd.DataFrame(rows)


def end_to_end_summary(df: pd.DataFrame) -> pd.DataFrame:
    s = df.groupby("category", sort=False).agg(questions=("passed", "size"), passed=("passed", "sum"))
    s["pass_rate"] = s.passed / s.questions
    return s.reset_index()
