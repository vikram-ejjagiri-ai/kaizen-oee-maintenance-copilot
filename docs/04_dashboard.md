# 04 – Dashboard Design

Code: `app/app.py` (Streamlit + Plotly) · Static versions: `src/plotting.py`

## Layout: from headline to cause
1. **KPI tiles:** OEE, A, P, Q, good parts, each with the change vs. the previous period of
   the same length. The first question is always "better or worse than before?".
2. **OEE by week per machine:** trends and outliers (the CNC-02 dip in week 31 is obvious).
3. **Loss waterfall:** where the planned time goes. In this plant the biggest block is
   speed loss and minor stops, followed by setups. That changes the improvement priority.
4. **Downtime Pareto:** which stop reasons matter. 80/20 rule: a few reasons cause most loss.
5. **Machine x shift heatmap:** finds shift effects (night shift on the press).
6. **Reliability table (MTBF/MTTR) and latest work orders:** link to maintenance.

Filters (period, machines, shifts) are in one place, the sidebar, and apply to everything.

## Design choices
- One colour per machine, always the same (CNC-01 blue, CNC-02 orange, ...), never by rank.
- Loss colours by OEE factor: red availability, yellow performance, violet quality.
- No dual-axis charts; the CNC-02 story uses two stacked charts instead.
- The waterfall y-axis does not start at 0 so small losses are visible, and the chart says so.

## Power BI option
`data/processed/shift_facts.csv` is the same fact table the app uses. Load it into Power BI
and build the measures as sums first, ratios second (DAX: `DIVIDE(SUM(good_ideal_min),
SUM(ppt_min))`). Never `AVERAGE` an OEE column.
