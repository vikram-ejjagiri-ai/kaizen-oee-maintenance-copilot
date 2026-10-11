# 02 – Data Model (MES + CMMS)

Code: `src/simulate.py` · Files: `data/*.csv` (generated)

## Tables
| Table | Grain (one row = ...) | Source system | Key columns |
|---|---|---|---|
| machines | machine | master data | machine_id, model, area |
| products | product on a machine | master data | product_id, machine_id, ideal_cycle_s |
| reason_codes | stop reason | master data | reason_code, kind (planned/unplanned), loss_group |
| events | state interval of a machine | MES | machine_id, start_ts, end_ts, state, reason_code |
| counts | product per machine-shift | MES | total_count, good_count, scrap_startup, scrap_process |
| alarms | alarm raised | machine PLC / SCADA | ts, machine_id, alarm_code, severity |
| work_orders | maintenance job | CMMS | wo_id, machine_id, type, symptom, cause, action, parts_used |

## Machine states
Every minute of a shift belongs to exactly one state:
- `RUNNING`
- `PLANNED_STOP` (reason BREAK or PM): not part of planned production time
- `DOWN` (all other reasons): unplanned stop, an availability loss

This "state log" design is how most MES and IIoT platforms store machine data. It is easy to
check: the events of a shift must add up to 480 minutes with no gaps and no overlaps.

## Reason code tree and the six big losses
Reason codes map to loss groups (`reason_codes.loss_group`):
- Equipment failure: BRK_TOOL, BRK_COOLANT, BRK_SPINDLE, VIBRATION, BRK_FEEDER, BRK_HYD,
  HYD_TEMP, SENSOR_LC, BRK_SCREW, ELEC
- Setup and adjustments: SETUP
- Organisational stop: MATERIAL, NO_OPERATOR

Performance and quality losses are not booked as stops. They are **calculated** from counts
and ideal cycle times. Stops shorter than 2 minutes are not booked in the MES
(SOP-ESC), so they appear as performance loss. That is realistic and important: a
machine that "never stops" can still have poor performance.

## Why simulate, and the planted stories
A simulation with known truth lets us test the analytics like code. Planted stories:
1. CNC-02 spindle bearing wear: rising A-217 warnings, slower cycles, more scrap, an ignored
   warning in a PM work order on 16 July, failure on 30 July.
2. PRESS-01: night-shift die changes take about twice as long; oil over-temperature during the
   July heat wave until the cooler is fixed on 24 July.
3. ASSY-01: light curtain faults (cleaning helps only briefly; a damaged cable is the real
   cause), material shortages on Monday mornings.
4. Data traps: duplicated count records and one shift booked with the wrong product.

## Moving to real data
Replace `simulate.py` with readers for the real systems (e.g. SQL views on the MES database,
CMMS export, OPC UA/MQTT events collected by the Kaizen factory stack). Everything after
`simulate.load()` keeps working if the tables keep these columns.
