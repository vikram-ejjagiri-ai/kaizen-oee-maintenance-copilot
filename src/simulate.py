"""Simulate 13 weeks of MES data for a small metal-parts plant.

Why simulate? Real MES data is confidential, and public OEE datasets are rare. A simulation
with known "stories" inside it also lets us check that the dashboard and the copilot find
what we planted, the same way a test checks code.

Planted stories (the dashboard and copilot should uncover these):
1. CNC-02: spindle bearing wears from early July. Vibration alarms (A-217), slower cycles,
   more scrap. A technician notes "vibration slightly elevated" on 16 July but no action is
   taken. The bearing fails on 30 July: about 17 hours of downtime.
2. PRESS-01: die changes take about twice as long on the night shift (SMED opportunity).
   During the July heat wave the hydraulic oil overheats (H-104) until the oil cooler is
   cleaned and its fan replaced on 24 July.
3. ASSY-01: frequent short stops from the light curtain (S-310). A cleaning on 2 July helps
   only for ten days; a damaged receiver cable is found and replaced on 12 August.
   Material shortages on Monday early shifts.
4. Two data-quality traps: a few duplicated count records (an MES re-send), and one shift
   booked with the wrong product code.

Output: CSV files in data/ (machines, products, reason_codes, events, counts, alarms,
work_orders).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from src import config

# --------------------------------------------------------------------------------------
# Master data
# --------------------------------------------------------------------------------------
MACHINES = pd.DataFrame(
    [
        ("CNC-01", "CNC turning center 1", "KMT TL-400", "Machining"),
        ("CNC-02", "CNC turning center 2", "KMT TL-400", "Machining"),
        ("PRESS-01", "Hydraulic press", "KMT HP-250", "Forming"),
        ("ASSY-01", "Assembly cell", "KMT AC-30", "Assembly"),
    ],
    columns=["machine_id", "name", "model", "area"],
)

PRODUCTS = pd.DataFrame(
    [
        ("SH-100", "Shaft short", "CNC-01", 48.0),
        ("SH-200", "Shaft long", "CNC-01", 62.0),
        ("SH-100", "Shaft short", "CNC-02", 48.0),
        ("SH-200", "Shaft long", "CNC-02", 62.0),
        ("BR-10", "Bracket small", "PRESS-01", 5.0),
        ("BR-20", "Bracket large", "PRESS-01", 7.0),
        ("AS-500", "Actuator 500", "ASSY-01", 30.0),
        ("AS-600", "Actuator 600", "ASSY-01", 36.0),
    ],
    columns=["product_id", "product_name", "machine_id", "ideal_cycle_s"],
)

# loss_group follows the "six big losses" idea; only availability losses are logged as
# stop reasons. Performance and quality losses are calculated from the counts.
REASON_CODES = pd.DataFrame(
    [
        ("BREAK", "Scheduled break", "planned", "Planned stop"),
        ("PM", "Planned preventive maintenance", "planned", "Planned stop"),
        ("SETUP", "Changeover / die change", "unplanned", "Setup and adjustments"),
        ("BRK_TOOL", "Tool breakage", "unplanned", "Equipment failure"),
        ("BRK_COOLANT", "Coolant system fault", "unplanned", "Equipment failure"),
        ("BRK_SPINDLE", "Spindle failure", "unplanned", "Equipment failure"),
        ("VIBRATION", "Spindle vibration alarm stop", "unplanned", "Equipment failure"),
        ("BRK_FEEDER", "Coil feeder jam", "unplanned", "Equipment failure"),
        ("BRK_HYD", "Hydraulic system fault", "unplanned", "Equipment failure"),
        ("HYD_TEMP", "Hydraulic oil over-temperature", "unplanned", "Equipment failure"),
        ("SENSOR_LC", "Light curtain fault", "unplanned", "Equipment failure"),
        ("BRK_SCREW", "Screwdriver unit fault", "unplanned", "Equipment failure"),
        ("ELEC", "Electrical fault", "unplanned", "Equipment failure"),
        ("MATERIAL", "Waiting for material", "unplanned", "Organisational stop"),
        ("NO_OPERATOR", "No operator available", "unplanned", "Organisational stop"),
    ],
    columns=["reason_code", "description", "kind", "loss_group"],
)

# Alarm raised when a stop of this reason starts.
REASON_ALARM = {
    "BRK_TOOL": ("A-305", "Tool breakage detected"),
    "BRK_COOLANT": ("A-101", "Coolant level / flow low"),
    "VIBRATION": ("A-217", "Spindle vibration high"),
    "BRK_SPINDLE": ("E-950", "Spindle drive fault"),
    "BRK_FEEDER": ("H-220", "Coil feeder jam"),
    "BRK_HYD": ("H-110", "Hydraulic pressure low"),
    "HYD_TEMP": ("H-104", "Hydraulic oil temperature high"),
    "SENSOR_LC": ("S-310", "Light curtain fault"),
    "BRK_SCREW": ("S-320", "Screwdriver torque fault"),
    "ELEC": ("E-910", "Drive / power supply fault"),
}


@dataclass
class MachineProfile:
    speed: float               # share of ideal speed reached while running (incl. minor stops)
    scrap_rate: float          # process scrap share
    startup_scrap: int         # parts scrapped after each changeover
    setup_rate: float          # changeovers per shift
    setup_median: dict         # shift -> median minutes
    pm: tuple                  # (weekday, shift, minutes) for weekly preventive maintenance
    stops: dict = field(default_factory=dict)  # reason -> (rate per shift, median min, sigma)


PROFILES = {
    "CNC-01": MachineProfile(0.88, 0.012, 2, 0.35, {"Early": 22, "Late": 22, "Night": 24},
                             (2, "Early", 90),
                             {"BRK_TOOL": (0.25, 14, 0.5), "BRK_COOLANT": (0.05, 45, 0.5),
                              "ELEC": (0.02, 60, 0.6), "MATERIAL": (0.10, 25, 0.5),
                              "NO_OPERATOR": (0.04, 30, 0.5)}),
    "CNC-02": MachineProfile(0.88, 0.012, 2, 0.35, {"Early": 22, "Late": 22, "Night": 24},
                             (3, "Early", 90),
                             {"BRK_TOOL": (0.25, 14, 0.5), "BRK_COOLANT": (0.05, 45, 0.5),
                              "ELEC": (0.02, 60, 0.6), "MATERIAL": (0.10, 25, 0.5),
                              "NO_OPERATOR": (0.04, 30, 0.5)}),
    "PRESS-01": MachineProfile(0.81, 0.006, 25, 0.85, {"Early": 38, "Late": 40, "Night": 74},
                               (1, "Early", 120),
                               {"BRK_FEEDER": (0.30, 12, 0.5), "BRK_HYD": (0.04, 90, 0.5),
                                "HYD_TEMP": (0.04, 25, 0.4), "ELEC": (0.02, 60, 0.6),
                                "MATERIAL": (0.12, 30, 0.5), "NO_OPERATOR": (0.04, 30, 0.5)}),
    "ASSY-01": MachineProfile(0.79, 0.009, 3, 0.30, {"Early": 14, "Late": 14, "Night": 15},
                              (4, "Late", 60),
                              {"SENSOR_LC": (0.80, 4, 0.4), "BRK_SCREW": (0.12, 20, 0.5),
                               "MATERIAL": (0.18, 35, 0.5), "ELEC": (0.02, 60, 0.6),
                               "NO_OPERATOR": (0.05, 30, 0.5)}),
}

BREAK_START_MIN, BREAK_MIN = 225, 30
SPINDLE_FAILURE = datetime(2026, 7, 30, 8, 40)
SPINDLE_REPAIR_MIN = 1020
WEAR_START = datetime(2026, 7, 6)
COOLER_FIX = datetime(2026, 7, 24, 11, 0)
LC_CLEANING = datetime(2026, 7, 2, 9, 30)
LC_CABLE_FIX = datetime(2026, 8, 12, 15, 10)
WRONG_PRODUCT_SHIFT = ("PRESS-01", date(2026, 8, 19), "Late")


# --------------------------------------------------------------------------------------
# Time-varying story factors
# --------------------------------------------------------------------------------------
def spindle_wear(t: datetime) -> float:
    """0 = healthy, 1 = about to fail. Reset after the repair."""
    if t < WEAR_START or t >= SPINDLE_FAILURE:
        return 0.0
    return (t - WEAR_START) / (SPINDLE_FAILURE - WEAR_START)


def heat(t: datetime) -> float:
    if date(2026, 7, 6) <= t.date() <= date(2026, 7, 26):
        return 1.0
    if t.month == 7:
        return 0.35
    if t.month == 8:
        return 0.25
    return 0.0


def stop_rate(machine: str, reason: str, base: float, t: datetime, shift: str) -> float:
    if machine == "CNC-02":
        w = spindle_wear(t)
        if reason == "BRK_TOOL":
            return base * (1 + 2 * w)
        if reason == "VIBRATION":
            return 3.0 * w
    if machine == "PRESS-01" and reason == "HYD_TEMP":
        rate = base + 1.1 * heat(t)
        return rate * (0.12 if t >= COOLER_FIX else 1.0)
    if machine == "ASSY-01":
        if reason == "SENSOR_LC":
            if t >= LC_CABLE_FIX:
                return 0.06
            if LC_CLEANING <= t < LC_CLEANING + timedelta(days=10):
                return 0.2
            return base
        if reason == "MATERIAL" and t.weekday() == 0 and shift == "Early":
            return 0.8
    return base


# --------------------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------------------
def production_shifts():
    d = config.START_DATE
    while d <= config.END_DATE:
        if d.weekday() < 5:
            for shift, hour in config.SHIFTS.items():
                yield d, shift, datetime.combine(d, datetime.min.time()) + timedelta(hours=hour)
        d += timedelta(days=1)


def _lognormal(rng, median, sigma):
    return max(2, int(round(median * np.exp(sigma * rng.standard_normal()))))


def simulate(seed: int = config.SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    events, counts, alarms = [], [], []
    products = {m: PRODUCTS[PRODUCTS.machine_id == m] for m in PROFILES}
    current_product = {m: products[m].product_id.iloc[0] for m in PROFILES}
    carry = {m: None for m in PROFILES}  # (reason, minutes left) spilling into next shift

    for shift_date, shift, start in production_shifts():
        for m, prof in PROFILES.items():
            n = config.SHIFT_MINUTES
            state = np.array(["RUNNING"] * n, dtype=object)
            # planned stops
            state[BREAK_START_MIN:BREAK_START_MIN + BREAK_MIN] = "BREAK"
            if shift_date.weekday() == prof.pm[0] and shift == prof.pm[1]:
                state[: prof.pm[2]] = "PM"

            def paint(first: int, minutes: int, reason: str) -> int:
                """Paint a stop onto running minutes. Returns minutes that did not fit."""
                i = first
                while i < n and minutes > 0:
                    if state[i] == "RUNNING" or state[i] == reason:
                        state[i] = reason
                    minutes -= 1
                    i += 1
                return minutes

            # stop carried over from the previous shift (e.g. the long spindle repair)
            if carry[m]:
                reason, left = carry[m]
                rest = paint(0, left, reason)
                carry[m] = (reason, rest) if rest > 0 else None

            # the planted spindle failure
            if m == "CNC-02" and start <= SPINDLE_FAILURE < start + timedelta(minutes=n):
                first = int((SPINDLE_FAILURE - start).total_seconds() // 60)
                rest = paint(first, SPINDLE_REPAIR_MIN, "BRK_SPINDLE")
                carry[m] = ("BRK_SPINDLE", rest) if rest > 0 else None

            # changeover
            changeover_at = None
            if rng.random() < prof.setup_rate:
                changeover_at = int(rng.integers(30, n - 60))
                setup_min = _lognormal(rng, prof.setup_median[shift], 0.3)
                if (m, shift_date, shift) == WRONG_PRODUCT_SHIFT:
                    changeover_at = None  # keep the trap shift single-product
                else:
                    paint(changeover_at, setup_min, "SETUP")
            if (m, shift_date, shift) == WRONG_PRODUCT_SHIFT:
                current_product[m] = "BR-10"

            # random unplanned stops
            mid = start + timedelta(hours=4)
            stop_specs = dict(prof.stops)
            if m == "CNC-02":
                stop_specs["VIBRATION"] = (0.0, 6, 0.4)
            for reason, (base, median, sigma) in stop_specs.items():
                k = rng.poisson(stop_rate(m, reason, base, mid, shift))
                for _ in range(k):
                    at = int(rng.integers(0, n - 5))
                    if state[at] != "RUNNING":
                        continue
                    paint(at, _lognormal(rng, median, sigma), reason)

            # compress minute states into events
            run_minutes_by_product = {}
            product = current_product[m]
            seg_start = 0
            for i in range(1, n + 1):
                if i == n or state[i] != state[seg_start]:
                    s = start + timedelta(minutes=seg_start)
                    e = start + timedelta(minutes=i)
                    st = state[seg_start]
                    events.append({
                        "machine_id": m, "shift_date": shift_date, "shift": shift,
                        "start_ts": s, "end_ts": e, "duration_min": i - seg_start,
                        "state": "RUNNING" if st == "RUNNING" else
                        ("PLANNED_STOP" if st in ("BREAK", "PM") else "DOWN"),
                        "reason_code": None if st == "RUNNING" else st,
                    })
                    if st in REASON_ALARM:
                        code, text = REASON_ALARM[st]
                        alarms.append({"ts": s, "machine_id": m, "alarm_code": code,
                                       "message": text, "severity": "fault"})
                    seg_start = i
            # running minutes per product (product switches at the changeover)
            for i in range(n):
                if changeover_at is not None and i == changeover_at:
                    others = products[m].product_id[products[m].product_id != product]
                    product = others.iloc[0]
                if state[i] == "RUNNING":
                    run_minutes_by_product[product] = run_minutes_by_product.get(product, 0) + 1
            current_product[m] = product

            # warning alarms that do not stop the machine
            w = spindle_wear(mid) if m == "CNC-02" else 0
            n_warn = rng.poisson(6 * w) if m == "CNC-02" else (
                rng.poisson(2 * heat(mid) * (0.12 if mid >= COOLER_FIX else 1)) if m == "PRESS-01" else 0)
            for _ in range(n_warn):
                code, text = ("A-217", "Spindle vibration high") if m == "CNC-02" else (
                    "H-104", "Hydraulic oil temperature high")
                alarms.append({"ts": start + timedelta(minutes=int(rng.integers(0, n))),
                               "machine_id": m, "alarm_code": code, "message": text,
                               "severity": "warning"})

            # counts
            speed = prof.speed - 0.20 * w
            scrap_rate = prof.scrap_rate + 0.05 * w
            for prod, run_min in run_minutes_by_product.items():
                ict = products[m].set_index("product_id").ideal_cycle_s[prod]
                total = int(run_min * 60 / ict * np.clip(speed + rng.normal(0, 0.02), 0.5, 0.99))
                startup = prof.startup_scrap if (changeover_at is not None and prod == product) else 0
                startup = min(startup, total)
                process = int(rng.binomial(total - startup, scrap_rate))
                booked = prod
                if (m, shift_date, shift) == WRONG_PRODUCT_SHIFT and prod == "BR-10":
                    booked = "BR-20"  # data-quality trap: wrong product booked
                counts.append({
                    "machine_id": m, "shift_date": shift_date, "shift": shift,
                    "product_id": booked, "total_count": total,
                    "good_count": total - startup - process,
                    "scrap_startup": startup, "scrap_process": process,
                })

    events = pd.DataFrame(events)
    events.insert(0, "event_id", [f"EV{i:06d}" for i in range(1, len(events) + 1)])
    counts = pd.DataFrame(counts)
    # data-quality trap: MES re-sent a few records
    dup = counts.sample(4, random_state=seed)
    counts = pd.concat([counts, dup]).sort_values(["shift_date", "machine_id"], kind="stable")
    alarms = pd.DataFrame(alarms).sort_values("ts").reset_index(drop=True)
    work_orders = make_work_orders(events, rng)
    return {
        "machines": MACHINES, "products": PRODUCTS, "reason_codes": REASON_CODES,
        "events": events, "counts": counts.reset_index(drop=True), "alarms": alarms,
        "work_orders": work_orders,
    }


# --------------------------------------------------------------------------------------
# Work orders (CMMS)
# --------------------------------------------------------------------------------------
WO_TEMPLATES = {
    "BRK_COOLANT": [
        ("Alarm A-101, coolant flow low, parts hot.", "Coolant filter clogged with chips.",
         "Cleaned chip basket and replaced coolant filter. Topped up coolant to 6 %.", "Coolant filter CF-20"),
        ("Coolant not reaching tool, A-101.", "Coolant pump intake blocked by swarf.",
         "Cleaned pump intake and tank, checked concentration (5.5 %).", ""),
    ],
    "ELEC": [
        ("Machine stopped with E-910 drive fault.", "Loose terminal on 24 V supply.",
         "Tightened terminals in cabinet, checked supply voltage 24.1 V.", ""),
        ("E-910 after restart, axis drive not ready.", "Cabinet fan clogged, drive overheated.",
         "Cleaned cabinet filter mat and fan, reset drive.", "Filter mat FM-3"),
    ],
    "BRK_FEEDER": [
        ("Coil feeder jam, H-220, strip buckled.", "Strip misaligned after coil change.",
         "Realigned strip guide, adjusted feeder rollers.", ""),
        ("Repeated H-220 feeder jams.", "Feeder roller worn.",
         "Replaced upper feeder roller, adjusted pressure.", "Feeder roller FR-8"),
    ],
    "BRK_HYD": [
        ("H-110 hydraulic pressure low, press stopped.", "Leaking hose fitting at main cylinder.",
         "Replaced hose and seal, refilled oil, pressure test OK.", "Hydraulic hose HH-12"),
        ("Pressure drops during stroke, H-110.", "Pressure relief valve setting drifted.",
         "Readjusted relief valve to spec, tested 10 strokes.", ""),
    ],
    "HYD_TEMP": [
        ("H-104 oil temperature high, press stopped to cool down.", "High ambient temperature.",
         "Let oil cool down, checked oil level OK. Cooler to be inspected.", ""),
        ("Repeated H-104 over-temperature.", "Oil cooler fins dirty.",
         "Blew out cooler fins with compressed air, restarted.", ""),
    ],
    "SENSOR_LC": [
        ("S-310 light curtain fault, operator reset several times.", "Dirt on light curtain lenses.",
         "Cleaned lenses, checked alignment.", ""),
        ("S-310 light curtain fault, intermittent.", "Unknown, could not reproduce.",
         "Checked alignment and connector, fault not present during check.", ""),
    ],
    "BRK_SCREW": [
        ("S-320 screwdriver torque fault, parts not tightened.", "Bit worn.",
         "Replaced screwdriver bit, verified torque with test joint.", "Screw bit SB-T25"),
        ("S-320 torque out of range.", "Screw feeder delivering wrong screws (mixed batch).",
         "Emptied and refilled feeder, informed logistics about mixed batch.", ""),
    ],
}

TECHS = ["T-01", "T-02", "T-03", "T-04", "T-05"]


def make_work_orders(events: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    down = events[events.state == "DOWN"]
    for ev in down.itertuples():
        r = ev.reason_code
        if r not in WO_TEMPLATES and r != "BRK_SPINDLE":
            continue
        # short stops are reset by the operator without a work order
        if r == "SENSOR_LC" and ev.duration_min < 6:
            continue
        if r in ("HYD_TEMP", "BRK_FEEDER") and ev.duration_min < 20:
            continue
        if r == "BRK_SPINDLE":
            continue  # written separately (story)
        symptom, cause, action, parts = WO_TEMPLATES[r][int(rng.integers(len(WO_TEMPLATES[r])))]
        rows.append(_wo(ev.start_ts, ev.machine_id, "Corrective", "High" if ev.duration_min > 45 else "Medium",
                        symptom, cause, action, parts, ev.duration_min, rng))

    # planned maintenance work orders
    pm = events[events.reason_code == "PM"]
    for ev in pm.itertuples():
        if ev.machine_id == "CNC-02" and ev.start_ts.date() == date(2026, 7, 16):
            continue  # this PM has its own story work order below
        model = MACHINES.set_index("machine_id").model[ev.machine_id]
        rows.append(_wo(ev.start_ts, ev.machine_id, "Preventive", "Low",
                        f"Weekly preventive maintenance {model}.", "Planned.",
                        "Completed weekly checklist: lubrication, filters, leaks, safety devices. No findings.",
                        "", 0, rng))

    # story work orders
    stories = [
        (datetime(2026, 7, 16, 7, 10), "CNC-02", "Preventive", "Low",
         "Weekly preventive maintenance KMT TL-400. Operator mentions more A-217 vibration warnings.",
         "Spindle vibration slightly elevated (4.8 mm/s, limit 7.1 mm/s). Possible bearing wear.",
         "Completed weekly checklist. Recommend bearing inspection at next opportunity. No parts ordered.",
         "", 0),
        (SPINDLE_FAILURE + timedelta(minutes=5), "CNC-02", "Corrective", "Urgent",
         "Spindle stopped with E-950 spindle drive fault after loud noise. Many A-217 warnings in last weeks.",
         "Front spindle bearing failed (spalling on outer race). Root cause: bearing wear not acted on after vibration trend.",
         "Replaced front and rear spindle bearing set, checked runout (2 um), run-in program 2 h, vibration 1.2 mm/s. "
         "Added monthly vibration measurement to PM plan.",
         "Spindle bearing set SB-7014", SPINDLE_REPAIR_MIN),
        (COOLER_FIX, "PRESS-01", "Corrective", "High",
         "Repeated H-104 oil over-temperature stops during heat wave.",
         "Oil cooler fins heavily clogged with dust, cooler fan bearing worn (fan slow).",
         "Cleaned oil cooler fins, replaced cooler fan motor. Oil temperature now 46 C at full load (before 61 C). "
         "Added cooler cleaning to monthly PM.",
         "Cooler fan motor CFM-250", 95),
        (LC_CLEANING, "ASSY-01", "Corrective", "Medium",
         "Frequent S-310 light curtain faults, about one per hour.",
         "Lenses dirty, receiver slightly misaligned.",
         "Cleaned emitter and receiver lenses, realigned receiver with alignment tool.", "", 25),
        (LC_CABLE_FIX, "ASSY-01", "Corrective", "High",
         "S-310 light curtain faults are back, often when the turntable moves.",
         "Receiver cable damaged at cable chain bend (intermittent break).",
         "Replaced receiver cable and rerouted it outside the cable chain bend. Tested with test rod, OK.",
         "Light curtain cable LCC-5", 40),
    ]
    for s in stories:
        rows.append(_wo(s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], rng))

    wo = pd.DataFrame(rows).sort_values("created_ts").reset_index(drop=True)
    day = wo.created_ts.dt.strftime("%y%m%d")
    wo.insert(0, "wo_id", "WO-" + day + "-" + (wo.groupby(day).cumcount() + 1).astype(str).str.zfill(2))
    return wo


def _wo(ts, machine, kind, prio, symptom, cause, action, parts, downtime, rng):
    return {
        "created_ts": ts + timedelta(minutes=int(rng.integers(2, 10))),
        "closed_ts": ts + timedelta(minutes=int(downtime) + int(rng.integers(15, 60))),
        "machine_id": machine, "type": kind, "priority": prio,
        "symptom": symptom, "cause": cause, "action": action,
        "parts_used": parts, "downtime_min": int(downtime),
        "technician": TECHS[int(rng.integers(len(TECHS)))],
    }


def save(tables: dict[str, pd.DataFrame]) -> None:
    config.DATA_DIR.mkdir(exist_ok=True)
    for name, df in tables.items():
        df.to_csv(config.DATA_DIR / f"{name}.csv", index=False)


def load() -> dict[str, pd.DataFrame]:
    """Load the CSVs with correct types."""
    names = ["machines", "products", "reason_codes", "events", "counts", "alarms", "work_orders"]
    t = {n: pd.read_csv(config.DATA_DIR / f"{n}.csv") for n in names}
    for c in ("start_ts", "end_ts"):
        t["events"][c] = pd.to_datetime(t["events"][c])
    t["events"]["shift_date"] = pd.to_datetime(t["events"]["shift_date"])
    t["counts"]["shift_date"] = pd.to_datetime(t["counts"]["shift_date"])
    t["alarms"]["ts"] = pd.to_datetime(t["alarms"]["ts"])
    for c in ("created_ts", "closed_ts"):
        t["work_orders"][c] = pd.to_datetime(t["work_orders"][c])
    t["work_orders"]["parts_used"] = t["work_orders"]["parts_used"].fillna("")
    return t


if __name__ == "__main__":
    tables = simulate()
    save(tables)
    for k, v in tables.items():
        print(f"{k:13s} {len(v):7,d} rows")
