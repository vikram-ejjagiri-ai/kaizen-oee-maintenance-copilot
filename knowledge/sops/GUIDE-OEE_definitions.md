---
doc_id: GUIDE-OEE
title: OEE definitions and loss categories used in this plant
machines: all
note: Written for this portfolio project, based on ISO 22400-2 and common TPM practice.
---

# OEE definitions used in this plant

## Time model
- **Shift time:** 8 hours (480 minutes). Production Monday to Friday in three shifts.
- **Planned production time (PPT):** shift time minus planned stops (breaks of 30 minutes and
  planned preventive maintenance).
- **Run time:** PPT minus unplanned stops (breakdowns, changeovers, waiting for material,
  missing operator).
- **Fully productive time:** good parts multiplied by ideal cycle time.

## The three OEE factors
- **Availability** = run time / planned production time. Lost by breakdowns, setups and
  organisational stops.
- **Performance** = (ideal cycle time x total parts) / run time. Lost by reduced speed and
  minor stops shorter than 2 minutes (these are not booked in the MES).
- **Quality** = good parts / total parts (weighted by ideal cycle time). Lost by startup
  rejects after changeovers and process scrap.
- **OEE** = Availability x Performance x Quality = fully productive time / PPT.

## Six big losses mapping
| Loss | OEE factor | How we see it |
|---|---|---|
| Equipment failure | Availability | stop reasons BRK_*, HYD_TEMP, SENSOR_LC, VIBRATION, ELEC |
| Setup and adjustments | Availability | stop reason SETUP |
| Organisational stops | Availability | MATERIAL, NO_OPERATOR |
| Idling and minor stops | Performance | missing parts vs. ideal speed |
| Reduced speed | Performance | missing parts vs. ideal speed |
| Process defects and startup rejects | Quality | scrap counts |

## Benchmarks
Typical discrete manufacturing OEE is 60-75 %. 85 % is often called world class. Comparing
OEE between different machine types is not meaningful; compare a machine with itself over
time and look at the losses.

## Aggregation rule
OEE of a week, a line or the plant is calculated from summed minutes and counts, never as an
average of shift OEE percentages. Averaging gives short or idle shifts too much weight.
