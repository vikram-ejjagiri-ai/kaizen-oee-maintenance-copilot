"""OEE engine (definitions follow ISO 22400-2 and common TPM practice).

    Planned production time (PPT) = shift time - planned stops (breaks, planned maintenance)
    Run time                      = PPT - unplanned stops (breakdowns, setups, waiting)
    Availability A = run time / PPT
    Performance  P = ideal cycle time x total count / run time
    Quality      Q = ideal cycle time x good count / (ideal cycle time x total count)
    OEE = A x P x Q = fully productive time / PPT

Q is weighted by ideal cycle time, so that A x P x Q is exactly "good parts made at ideal
speed / planned time" even when a machine makes several products.

Golden rule: aggregate MINUTES first, then divide. Never average OEE percentages across
shifts or machines (see `aggregate` and tests/test_oee.py).
"""
from __future__ import annotations

import pandas as pd

KEYS = ["machine_id", "shift_date", "shift"]
LOSS_GROUPS = ["Equipment failure", "Setup and adjustments", "Organisational stop"]


def shift_facts(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per machine and shift with all minutes and counts. The base fact table."""
    ev = t["events"].merge(t["reason_codes"][["reason_code", "loss_group"]], on="reason_code", how="left")
    minutes = ev.pivot_table(index=KEYS, columns="state", values="duration_min",
                             aggfunc="sum", fill_value=0)
    for col in ("RUNNING", "PLANNED_STOP", "DOWN"):
        if col not in minutes:
            minutes[col] = 0
    losses = (ev[ev.state == "DOWN"].pivot_table(index=KEYS, columns="loss_group", values="duration_min",
                                                 aggfunc="sum", fill_value=0)
              .reindex(columns=LOSS_GROUPS, fill_value=0))
    c = t["counts"].merge(t["products"][["machine_id", "product_id", "ideal_cycle_s"]],
                          on=["machine_id", "product_id"], how="left")
    c["ideal_min"] = c.total_count * c.ideal_cycle_s / 60
    c["good_ideal_min"] = c.good_count * c.ideal_cycle_s / 60
    c["scrap_count"] = c.scrap_startup + c.scrap_process
    counts = c.groupby(KEYS)[["total_count", "good_count", "scrap_count", "scrap_startup",
                              "scrap_process", "ideal_min", "good_ideal_min"]].sum()

    f = pd.DataFrame({
        "calendar_min": minutes[["RUNNING", "PLANNED_STOP", "DOWN"]].sum(axis=1),
        "planned_stop_min": minutes["PLANNED_STOP"],
        "down_min": minutes["DOWN"],
        "run_min": minutes["RUNNING"],
    }).join(losses).join(counts).fillna(0).reset_index()
    f["ppt_min"] = f.calendar_min - f.planned_stop_min
    f["shift_date"] = pd.to_datetime(f.shift_date)
    iso = f.shift_date.dt.isocalendar()
    f["week"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
    f["month"] = f.shift_date.dt.strftime("%Y-%m")
    return f


def ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Add A, P, Q, OEE to a frame that holds SUMMED minutes and counts."""
    df = df.copy()
    df["availability"] = df.run_min / df.ppt_min.where(df.ppt_min > 0)
    df["performance"] = df.ideal_min / df.run_min.where(df.run_min > 0)
    df["quality"] = df.good_ideal_min / df.ideal_min.where(df.ideal_min > 0)
    df["oee"] = df.good_ideal_min / df.ppt_min.where(df.ppt_min > 0)
    df["scrap_rate"] = df.scrap_count / df.total_count.where(df.total_count > 0)
    return df


SUM_COLS = ["calendar_min", "planned_stop_min", "ppt_min", "down_min", "run_min", *LOSS_GROUPS,
            "total_count", "good_count", "scrap_count", "scrap_startup", "scrap_process",
            "ideal_min", "good_ideal_min"]


def aggregate(facts: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Sum minutes and counts, THEN compute ratios. by=None gives one total row."""
    if not by:
        return ratios(facts[SUM_COLS].sum().to_frame().T)
    return ratios(facts.groupby(by, as_index=False)[SUM_COLS].sum())


def filter_facts(facts: pd.DataFrame, start=None, end=None, machines=None, shifts=None) -> pd.DataFrame:
    m = pd.Series(True, index=facts.index)
    if start is not None:
        m &= facts.shift_date >= pd.Timestamp(start)
    if end is not None:
        m &= facts.shift_date <= pd.Timestamp(end)
    if machines:
        m &= facts.machine_id.isin(machines)
    if shifts:
        m &= facts["shift"].isin(shifts)
    return facts[m]


def loss_waterfall(facts: pd.DataFrame) -> pd.DataFrame:
    """Minutes from planned production time down to fully productive time."""
    s = facts[SUM_COLS].sum()
    perf_loss = s.run_min - s.ideal_min
    qual_loss = s.ideal_min - s.good_ideal_min
    rows = [("Planned production time", s.ppt_min, "total")]
    rows += [(g, -s[g], "availability") for g in LOSS_GROUPS]
    rows += [("Speed loss and minor stops", -perf_loss, "performance"),
             ("Scrap and startup rejects", -qual_loss, "quality"),
             ("Fully productive time", s.good_ideal_min, "total")]
    return pd.DataFrame(rows, columns=["step", "minutes", "category"])


def downtime_pareto(t: dict[str, pd.DataFrame], start=None, end=None, machines=None, shifts=None) -> pd.DataFrame:
    ev = t["events"]
    ev = ev[ev.state == "DOWN"]
    if start is not None:
        ev = ev[ev.shift_date >= pd.Timestamp(start)]
    if end is not None:
        ev = ev[ev.shift_date <= pd.Timestamp(end)]
    if machines:
        ev = ev[ev.machine_id.isin(machines)]
    if shifts:
        ev = ev[ev["shift"].isin(shifts)]
    p = (ev.merge(t["reason_codes"], on="reason_code")
         .groupby(["reason_code", "description", "loss_group"], as_index=False)
         .agg(minutes=("duration_min", "sum"), stops=("duration_min", "size"))
         .sort_values("minutes", ascending=False))
    p["share"] = p.minutes / p.minutes.sum() if len(p) else 0
    p["cumulative_share"] = p.share.cumsum()
    return p.reset_index(drop=True)


def failure_incidents(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge stop segments that belong to one failure (a repair can span breaks and shifts)."""
    ev = t["events"].merge(t["reason_codes"][["reason_code", "loss_group"]], on="reason_code", how="left")
    ev = ev[ev.state != "PLANNED_STOP"].sort_values(["machine_id", "start_ts"])
    rows = []
    for m, g in ev.groupby("machine_id"):
        cur = None
        for r in g.itertuples():
            same = (cur is not None and r.state == "DOWN" and r.reason_code == cur["reason_code"]
                    and (r.start_ts - cur["end_ts"]).total_seconds() <= 3600)
            if same:
                cur["end_ts"] = r.end_ts
                cur["repair_min"] += r.duration_min
                continue
            if cur is not None:
                rows.append(cur)
            cur = None
            if r.state == "DOWN" and r.loss_group == "Equipment failure":
                cur = {"machine_id": m, "reason_code": r.reason_code, "start_ts": r.start_ts,
                       "end_ts": r.end_ts, "repair_min": r.duration_min}
        if cur is not None:
            rows.append(cur)
    return pd.DataFrame(rows, columns=["machine_id", "reason_code", "start_ts", "end_ts", "repair_min"])


def reliability(t: dict[str, pd.DataFrame], facts: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """MTBF (run hours between failures) and MTTR (minutes per repair) per machine."""
    inc = failure_incidents(t)
    if start is not None:
        inc = inc[inc.start_ts >= pd.Timestamp(start)]
    if end is not None:
        inc = inc[inc.start_ts < pd.Timestamp(end) + pd.Timedelta(days=1)]
    f = filter_facts(facts, start, end)
    run_h = f.groupby("machine_id").run_min.sum() / 60
    n = inc.groupby("machine_id").size()
    rep = inc.groupby("machine_id").repair_min.sum()
    out = pd.DataFrame({"run_hours": run_h, "failures": n, "repair_min": rep}).fillna(0)
    out["mtbf_h"] = out.run_hours / out.failures.where(out.failures > 0)
    out["mttr_min"] = out.repair_min / out.failures.where(out.failures > 0)
    return out.reset_index().rename(columns={"index": "machine_id"})
