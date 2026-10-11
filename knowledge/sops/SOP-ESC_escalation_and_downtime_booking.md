---
doc_id: SOP-ESC
title: SOP Escalation and downtime booking
machines: all
note: Fictional demo SOP for this portfolio project.
---

# SOP Escalation and downtime booking

## Booking stop reasons in the MES
Every stop longer than 2 minutes must get a reason code at the MES terminal. Shorter stops are
not booked and appear as performance loss. Use the most specific code (e.g. SENSOR_LC instead
of ELEC). Unbooked stops make OEE analysis useless.
Important codes: SETUP (changeover/die change), MATERIAL (waiting for material),
NO_OPERATOR, BRK_* (breakdowns by assembly), HYD_TEMP, SENSOR_LC, VIBRATION, ELEC.

## When to call maintenance
- Immediately: any safety device fault, leaks of oil or coolant on the floor, smoke, unusual
  noise, E-950 spindle drive fault, H-110 hydraulic pressure low.
- After the second occurrence in one shift: tool breakage, feeder jams, torque faults.
- Light curtain fault S-310: after the third reset in one shift.
- Warnings (A-217, H-104 warning level): note them in the shift handover; if they repeat on
  several days, create a work order for inspection.

## Escalation times
- Stop longer than 15 minutes: inform the shift leader.
- Stop longer than 60 minutes: shift leader informs the production manager and logistics
  (delivery risk).
- Repeated failures of the same type (3 or more in a week): maintenance planner opens a
  root-cause analysis (5 Why) and checks the preventive maintenance plan.

## Creating a good work order
Describe the symptom (what the operator saw, alarm codes), the cause found, the action taken,
parts used and the downtime. "Fixed" is not a description. Good work orders are what makes
history searchable for the next technician.
