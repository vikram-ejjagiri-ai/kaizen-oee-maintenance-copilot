"""Data-quality checks. MES data is never perfect, and an OEE number is only as good as the
events and counts behind it. Every check returns a row for the report; fixes are explicit
and documented, never silent.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src import config

# Corrections confirmed with the production team. Each one is documented, never silent.
# (machine, shift_date, shift, booked product) -> correct product
KNOWN_CORRECTIONS = {
    ("PRESS-01", "2026-08-19", "Late", "BR-20"): (
        "BR-10",
        "Shift leader confirmed: BR-10 was produced, BR-20 was booked by mistake.",
    ),
}


@dataclass
class CheckResult:
    check: str
    status: str   # OK / FIXED / WARNING / ERROR
    detail: str


def run_checks(t: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], list[CheckResult]]:
    t = {k: v.copy() for k, v in t.items()}
    results: list[CheckResult] = []
    ev, cnt = t["events"], t["counts"]

    # 1. duplicated count records (MES re-sends the same record)
    dups = cnt.duplicated(keep="first")
    cnt = cnt[~dups].copy()
    results.append(CheckResult(
        "Duplicate count records", "FIXED" if dups.any() else "OK",
        f"{int(dups.sum())} exact duplicate records (MES re-sends) removed." if dups.any() else "None found."))
    key = ["machine_id", "shift_date", "shift", "product_id"]
    clash = cnt.duplicated(key, keep=False)
    if clash.any():
        results.append(CheckResult("Conflicting count records", "WARNING",
                                   f"{int(clash.sum())} records share a key but differ in values."))

    # 2. every machine-shift must be fully covered by events (480 min, no overlaps)
    cover = ev.groupby(["machine_id", "shift_date", "shift"]).duration_min.sum()
    bad = cover[cover != config.SHIFT_MINUTES]
    ev_sorted = ev.sort_values(["machine_id", "start_ts"])
    overlap = (ev_sorted.start_ts < ev_sorted.groupby("machine_id").end_ts.shift()).sum()
    results.append(CheckResult(
        "Event timeline complete", "OK" if bad.empty and overlap == 0 else "ERROR",
        f"{len(cover)} machine-shifts checked, {len(bad)} with gaps, {int(overlap)} overlapping events."))

    # 3. unknown reason codes
    known = set(t["reason_codes"].reason_code)
    unknown = set(ev.reason_code.dropna()) - known
    results.append(CheckResult("Reason codes valid", "OK" if not unknown else "ERROR",
                               "All reason codes in master data." if not unknown else f"Unknown: {unknown}"))

    # 4. count arithmetic
    wrong = (cnt.good_count + cnt.scrap_startup + cnt.scrap_process != cnt.total_count) | (
        cnt[["total_count", "good_count", "scrap_startup", "scrap_process"]] < 0).any(axis=1)
    results.append(CheckResult("Good + scrap = total", "OK" if not wrong.any() else "ERROR",
                               f"{int(wrong.sum())} records inconsistent."))

    # 5. physically impossible performance (> 105 %) -> usually wrong product or cycle time
    perf = _shift_performance(ev, cnt, t["products"])
    impossible = perf[perf.performance > 1.05]
    fixed = []
    for row in impossible.itertuples():
        for prod in cnt[(cnt.machine_id == row.machine_id) & (cnt.shift_date == row.shift_date)
                        & (cnt["shift"] == row.shift)].product_id:
            k = (row.machine_id, pd.Timestamp(row.shift_date).strftime("%Y-%m-%d"), row.shift, prod)
            if k in KNOWN_CORRECTIONS:
                new, why = KNOWN_CORRECTIONS[k]
                mask = ((cnt.machine_id == row.machine_id) & (cnt.shift_date == row.shift_date)
                        & (cnt["shift"] == row.shift) & (cnt.product_id == prod))
                cnt.loc[mask, "product_id"] = new
                fixed.append(f"{k[0]} {k[1]} {k[2]}: {prod} -> {new} ({why})")
    if impossible.empty:
        results.append(CheckResult("Performance <= 105 %", "OK", "No impossible shifts."))
    else:
        open_ = len(impossible) - len(fixed)
        detail = f"{len(impossible)} shift(s) above 105 %. " + " ".join(fixed)
        if open_:
            detail += f" {open_} not yet explained."
        results.append(CheckResult("Performance <= 105 %", "FIXED" if not open_ else "WARNING", detail))

    # 6. work orders closed before they were created
    wo = t["work_orders"]
    neg = (wo.closed_ts < wo.created_ts).sum()
    results.append(CheckResult("Work order timestamps", "OK" if neg == 0 else "ERROR",
                               f"{len(wo)} work orders, {int(neg)} closed before created."))

    t["counts"] = cnt.reset_index(drop=True)
    return t, results


def _shift_performance(ev, cnt, products) -> pd.DataFrame:
    run = (ev[ev.state == "RUNNING"].groupby(["machine_id", "shift_date", "shift"])
           .duration_min.sum().rename("run_min"))
    c = cnt.merge(products[["machine_id", "product_id", "ideal_cycle_s"]],
                  on=["machine_id", "product_id"], how="left")
    c["ideal_min"] = c.total_count * c.ideal_cycle_s / 60
    ideal = c.groupby(["machine_id", "shift_date", "shift"]).ideal_min.sum()
    df = pd.concat([run, ideal], axis=1).fillna(0).reset_index()
    df["performance"] = df.ideal_min / df.run_min.where(df.run_min > 0)
    return df


def results_frame(results: list[CheckResult]) -> pd.DataFrame:
    return pd.DataFrame([r.__dict__ for r in results])
