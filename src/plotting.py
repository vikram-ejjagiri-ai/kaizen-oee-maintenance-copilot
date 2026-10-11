"""Static figures for the report and README (the interactive versions live in the app)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import config, oee

# Validated categorical palette (fixed order, colour follows the machine, never its rank)
MACHINE_COLORS = {"CNC-01": "#2a78d6", "CNC-02": "#eb6834", "PRESS-01": "#1baf7a", "ASSY-01": "#eda100"}
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LOSS = {"availability": "#e34948", "performance": "#eda100", "quality": "#6250d6", "total": "#2a78d6"}


def _style(ax, title: str, subtitle: str | None = None):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold", pad=22 if subtitle else 10)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2)


def _save(fig, name: str):
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.patch.set_facecolor(SURFACE)
    fig.savefig(config.FIGURES_DIR / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


def oee_by_week(facts: pd.DataFrame):
    w = oee.aggregate(facts, ["week", "machine_id"])
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ends = {}
    for m, color in MACHINE_COLORS.items():
        d = w[w.machine_id == m]
        ax.plot(d.week, d.oee * 100, color=color, linewidth=2, marker="o", markersize=4, label=m)
        ends[m] = (d.week.iloc[-1], d.oee.iloc[-1] * 100)
    # direct labels at the line ends, pushed apart so they never overlap
    placed = []
    for m, (x, y) in sorted(ends.items(), key=lambda kv: kv[1][1]):
        y_lab = max([y] + [p + 2.2 for p in placed])
        placed.append(y_lab)
        ax.annotate(m, (x, y), xytext=(x, y_lab), textcoords="data", va="center", fontsize=9, color=INK_2,
                    ha="left", annotation_clip=False)
        ax.texts[-1].set_position((len(w.week.unique()) - 1 + 0.25, y_lab))
    ax.set_ylabel("OEE %", color=INK_2, fontsize=9)
    ax.set_xticks(range(len(w.week.unique())))
    ax.set_xticklabels([x[-3:] for x in sorted(w.week.unique())])
    ax.set_ylim(45, None)
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="lower left")
    _style(ax, "OEE by week and machine", "Calculated from summed minutes per week (ISO weeks, June to August 2026)")
    _save(fig, "oee_by_week.png")


def loss_waterfall(facts: pd.DataFrame):
    wf = oee.loss_waterfall(facts)
    ppt = wf.minutes.iloc[0]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    level = 0.0
    for i, r in enumerate(wf.itertuples()):
        if r.category == "total":
            bottom, height = 0, r.minutes
            level = r.minutes
        else:
            bottom, height = level + r.minutes, -r.minutes
            level += r.minutes
        ax.bar(i, height / 60, bottom=bottom / 60, color=LOSS[r.category], width=0.6)
        ax.text(i, (bottom + height) / 60 + ppt / 60 * 0.015, f"{abs(r.minutes) / ppt * 100:.1f} %",
                ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(wf)))
    ax.set_xticklabels([s.replace(" and ", " &\n").replace("Planned production time", "Planned\nproduction time")
                        .replace("Fully productive time", "Fully\nproductive time").replace("Organisational stop", "Organisational\nstop")
                        .replace("Equipment failure", "Equipment\nfailure") for s in wf.step], fontsize=8.5)
    ax.set_ylabel("hours", color=INK_2, fontsize=9)
    ax.set_ylim(ppt / 60 * 0.6, ppt / 60 * 1.05)
    _style(ax, "Where the planned production time goes (all machines)",
           "Red = availability losses, yellow = performance, violet = quality. Y-axis starts at 60 %.")
    _save(fig, "loss_waterfall.png")


def downtime_pareto(t: dict):
    p = oee.downtime_pareto(t).head(8).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.barh(p.description, p.minutes / 60, color="#2a78d6", height=0.6)
    for y, r in enumerate(p.itertuples()):
        ax.text(r.minutes / 60 + 2, y, f"{r.minutes / 60:.0f} h  ({r.share * 100:.0f} %, {r.stops} stops)",
                va="center", fontsize=8.5, color=INK)
    ax.grid(axis="x", color=GRID)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, p.minutes.max() / 60 * 1.35)
    ax.set_xlabel("hours of unplanned downtime", color=INK_2, fontsize=9)
    _style(ax, "Downtime Pareto: top 8 stop reasons (all machines, 13 weeks)")
    _save(fig, "downtime_pareto.png")


def cnc02_story(t: dict, facts: pd.DataFrame):
    f = facts[facts.machine_id == "CNC-02"]
    w = oee.aggregate(f, ["week"])
    al = t["alarms"][(t["alarms"].machine_id == "CNC-02") & (t["alarms"].alarm_code == "A-217")]
    iso = al.ts.dt.isocalendar()
    al_w = (iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)).value_counts()
    al_w = al_w.reindex(w.week, fill_value=0)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True, gridspec_kw={"hspace": 0.45})
    x = range(len(w))
    a1.plot(x, w.oee * 100, color=MACHINE_COLORS["CNC-02"], linewidth=2, marker="o", markersize=4)
    a2.bar(x, al_w.values, color=MACHINE_COLORS["CNC-02"], width=0.6)
    weeks = list(w.week)
    for label, wk, ha, dx in (("16 Jul: technician notes\nelevated vibration", "2026-W29", "right", -6),
                              ("30 Jul: spindle bearing\nfails, ~17 h down", "2026-W31", "left", 6)):
        i = weeks.index(wk)
        for ax in (a1, a2):
            ax.axvline(i, color=INK_2, linestyle="--", linewidth=1)
        a1.annotate(label, (i, 60), xytext=(dx, 0), textcoords="offset points", ha=ha, fontsize=8, color=INK)
    a1.set_ylim(50, 95)
    a1.set_ylabel("OEE %", color=INK_2, fontsize=9)
    a2.set_ylabel("A-217 alarms", color=INK_2, fontsize=9)
    a2.set_xticks(list(x))
    a2.set_xticklabels([wk[-3:] for wk in weeks])
    _style(a1, "CNC-02: the failure that announced itself", "Weekly OEE")
    _style(a2, "", "Spindle vibration alarms (A-217) per week")
    _save(fig, "cnc02_story.png")


def press_setup_by_shift(setup: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.bar(setup["shift"], setup.avg_min, color=MACHINE_COLORS["PRESS-01"], width=0.55)
    for i, r in enumerate(setup.itertuples()):
        ax.text(i, r.avg_min + 1.5, f"{r.avg_min:.0f} min\n({r.changeovers} die changes)", ha="center",
                fontsize=8.5, color=INK)
    ax.axhline(35, color=INK_2, linestyle="--", linewidth=1)
    ax.text(-0.45, 30, "target 35 min", fontsize=8, color=INK_2, ha="left")
    ax.set_ylim(0, setup.avg_min.max() * 1.35)
    ax.set_ylabel("average minutes", color=INK_2, fontsize=9)
    _style(ax, "PRESS-01: average die change time by shift")
    _save(fig, "press_setup_by_shift.png")
