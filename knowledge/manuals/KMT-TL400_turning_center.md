---
doc_id: MAN-TL400
title: KMT TL-400 CNC turning center - operation and maintenance manual
machines: CNC-01, CNC-02
note: Fictional demo manual written for this portfolio project.
---

# KMT TL-400 CNC turning center

## Overview
The KMT TL-400 is a 2-axis CNC turning center for shafts up to 400 mm long. Main assemblies:
main spindle with front and rear angular contact bearings, 12-station tool turret, coolant
system (tank 180 l, pump, filter CF-20, chip conveyor) and electrical cabinet with axis drives.
Machines in this plant: CNC-01 and CNC-02.

## Safety before any maintenance
Before opening covers, reaching into the working area or working in the electrical cabinet,
stop the machine and apply lockout/tagout according to SOP-LOTO. The door interlock and the
emergency stop must never be bridged or bypassed. Only qualified electricians may work in the
cabinet. The spindle can coast for several seconds after a stop: wait until it has stopped.

## Alarm A-101 Coolant level or flow low
**Meaning:** The coolant flow switch does not detect enough flow, or the tank level is low.
**Effects:** Parts run hot, poor surface finish, faster tool wear. The machine stops at the
end of the cycle.
**Troubleshooting:**
1. Check the tank level; top up with coolant mixed to 5-7 % concentration (refractometer).
2. Empty the chip basket and check filter CF-20; replace it if clogged.
3. Check the pump intake for swarf; clean the tank if a lot of fine chips have settled.
4. If flow is still low, check the pump motor current and contact maintenance.

## Alarm A-217 Spindle vibration high
**Meaning:** The spindle vibration sensor measures a vibration velocity above the warning
limit (4.5 mm/s RMS). Above 7.1 mm/s the machine stops.
**Typical causes:** worn or damaged spindle bearings, unbalanced workpiece or chuck, loose
tool or turret, chatter from wrong cutting data.
**Troubleshooting:**
1. Check the workpiece clamping and chuck jaws; check that the tool is tight.
2. Check cutting data against the program sheet; reduce speed if chatter marks are visible.
3. If A-217 warnings repeat over several days with correct clamping and cutting data, the
   spindle bearings are the most likely cause. Request a vibration measurement by maintenance.
**Important:** A rising trend of A-217 warnings is an early warning of bearing damage. Do not
just reset the alarm repeatedly. Plan a bearing inspection: a planned bearing replacement
takes about 6 hours, a bearing failure in operation usually causes 12-20 hours of downtime
and can damage the spindle shaft.

## Alarm A-305 Tool breakage detected
**Meaning:** The tool monitoring system detected a sudden drop in cutting force or the
broken-tool probe did not find the tool tip.
**Troubleshooting:**
1. Lock out the machine, open the door and check the tool. Replace the insert or tool.
2. Remove broken pieces from the workpiece and chip area. Scrap the affected part.
3. Check tool life counters; frequent breakage can be caused by vibration (see A-217),
   wrong cutting data or poor insert quality.
Tool changes after breakage are done by the operator and do not need a work order unless
breakage repeats more than three times per shift.

## Alarm E-910 Drive or power supply fault
**Meaning:** An axis or spindle drive reports "not ready", or the 24 V control supply dropped.
**Troubleshooting (qualified electrician only):**
1. Read the drive fault number on the drive display and note it in the work order.
2. Check the cabinet temperature, the cabinet fan and filter mat (clogged filters cause drive
   overheating).
3. Check 24 V supply voltage (23.5-24.5 V) and terminal tightness.

## Alarm E-950 Spindle drive fault
**Meaning:** The spindle drive stopped because of overcurrent, overtemperature or a blocked
spindle. Often follows mechanical spindle damage.
**Action:** Do not restart repeatedly. Lock out the machine and call maintenance. Check whether
the spindle turns freely by hand (machine locked out) and listen for noise. If bearing damage
is suspected, the spindle bearing set SB-7014 must be replaced (see Spindle bearing replacement).

## Spindle bearing replacement
Performed by maintenance only, two technicians, about 6 hours planned (longer after a failure
because the spindle housing must be cleaned and checked).
1. Lock out the machine (SOP-LOTO). Remove chuck and spindle cover.
2. Remove drive belt and rear nut; press out the spindle with the extraction tool.
3. Replace front and rear bearings as a set (SB-7014). Never replace only one bearing.
4. Heat bearings to max. 80 C for mounting; preload according to the spindle data sheet.
5. Run-in program: 2 hours with stepped speeds. Check runout (< 3 um) and vibration (< 2 mm/s).
6. Record vibration value in the work order as the new baseline.

## Preventive maintenance plan
**Daily (operator):** check coolant level and concentration, clean chips from the working area,
check lubrication oil level, test door interlock.
**Weekly (maintenance, about 90 min):** clean coolant filter, check chuck jaw wear, grease
chuck, check hydraulic unit pressure, inspect way covers, check for leaks.
**Monthly:** measure spindle vibration and record the trend (warning 4.5 mm/s, stop 7.1 mm/s),
clean cabinet filter mats, check turret clamping.
**Yearly:** geometry check, ball screw backlash check, replace hydraulic oil.

## Typical cycle times and quality
Ideal cycle time SH-100: 48 s, SH-200: 62 s. Typical scrap rate below 1.5 %. Higher scrap with
chatter marks on the surface is often linked to spindle vibration (A-217) or worn inserts.
