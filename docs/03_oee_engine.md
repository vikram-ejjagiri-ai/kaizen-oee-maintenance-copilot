# 03 – OEE Engine and Data Checks

Code: `src/oee.py`, `src/checks.py` · Tests: `tests/test_oee.py`

## Definitions (ISO 22400-2, TPM practice)
```
Shift time                 480 min
- planned stops            breaks, planned maintenance
= Planned production time  (PPT)
- unplanned stops          breakdowns, setups, waiting
= Run time
Availability A = run time / PPT
Performance  P = ideal cycle time x total parts / run time
Quality      Q = ideal cycle time x good parts / (ideal cycle time x total parts)
OEE = A x P x Q = good parts x ideal cycle time / PPT  ("fully productive time" / PPT)
```
Example: PPT 450 min, 30 min breakdown -> run 420 min, A = 93.3 %. Ideal cycle 48 s, 470
parts -> 376 min at ideal speed, P = 89.5 %. 9 parts scrap -> Q = 98.1 %. OEE = 82.0 % (= 461 good x 48 s / 450 min).

## The two classic mistakes (and how the code avoids them)
1. **Averaging percentages.** The OEE of a week is NOT the average of shift OEEs. A short
   shift with bad OEE would count as much as a full shift. `oee.aggregate()` always sums
   minutes and counts first, then divides. A test proves the difference.
2. **Mixing products.** With several products, Q is weighted by ideal cycle time, so that
   A x P x Q is exactly fully productive time / PPT.

## Base fact table
`shift_facts()` builds one row per machine and shift with all minutes and counts. Every
chart and every copilot answer is computed from this table, so all numbers agree.

## Other KPIs
- **Loss waterfall:** PPT -> minus each availability loss group -> minus performance loss
  -> minus quality loss -> fully productive time (`loss_waterfall`).
- **Downtime Pareto:** minutes and number of stops per reason (`downtime_pareto`).
- **MTBF / MTTR:** for equipment failures. A repair that runs through a break or into the next
  shift is split into several events in the MES; `failure_incidents()` merges them back so a
  17-hour repair counts as one failure, not five.

## Data checks (`checks.py`)
| Check | Why |
|---|---|
| Duplicate count records | MES interfaces re-send messages; duplicates inflate output |
| Timeline complete | each shift must have exactly 480 minutes of events |
| Reason codes valid | unknown codes break the loss mapping |
| Good + scrap = total | basic arithmetic of counts |
| Performance <= 105 % | above 100 % is physically impossible: wrong product or wrong ideal cycle time |
| Work order timestamps | closed before created = data entry error |

Fixes are **explicit**: duplicates are removed and counted; the wrong product booking is
corrected through `KNOWN_CORRECTIONS` with the reason written next to it. In a real plant
this list is reviewed with the production team. Silent fixes destroy trust in a KPI.
