---
doc_id: MAN-AC30
title: KMT AC-30 assembly cell - operation and maintenance manual
machines: ASSY-01
note: Fictional demo manual written for this portfolio project.
---

# KMT AC-30 assembly cell

## Overview
The KMT AC-30 is a semi-automated assembly cell for actuators. The operator loads parts into a
rotating turntable with four stations: press-fit, screwdriving (electric screwdriver unit with
torque control), leak test and marking. The loading station is protected by a safety light
curtain. Machine in this plant: ASSY-01.

## Safety before any maintenance
The light curtain stops the turntable when the operator reaches into the cell. Never bypass,
mute or bridge the light curtain, not even "for a quick test". Before work inside the cell,
stop the cell and apply lockout/tagout (SOP-LOTO), including compressed air. After any work on
the light curtain, test it with the test rod at several heights before restarting.

## Alarm S-310 Light curtain fault
**Meaning:** The light curtain controller reports an internal fault or lost synchronisation
between emitter and receiver. This is different from a normal light curtain interruption
(operator reaching in), which only stops the turntable.
**Typical causes:**
- dirty emitter or receiver lenses
- misalignment after a knock
- damaged or loose cable or connector, often where the cable moves (cable chain, turntable)
- strong external light or reflections
**Troubleshooting:**
1. Clean both lenses with a soft cloth.
2. Check the alignment LEDs; realign with the alignment tool if needed.
3. If faults are intermittent and continue after cleaning and alignment, check cables and
   connectors along their full length, especially at bends and moving parts. Intermittent
   cable breaks often appear only when the cable moves.
4. Test with the test rod after every intervention.
**Note:** Repeated S-310 faults that operators reset many times per shift cause a large hidden
loss. If cleaning does not solve it for more than a week, look for a cable or connector fault.

## Alarm S-320 Screwdriver torque fault
**Meaning:** The final torque or angle of a screw joint is outside the tolerance window.
**Troubleshooting:** check the screwdriver bit for wear (replace SB-T25), check that the
correct screws are in the feeder (mixed batches cause torque faults), check the test joint
with the torque analyzer. The affected part must be reworked or scrapped.

## Alarm S-330 Part missing
**Meaning:** A sensor at a station did not detect the expected part. Check part presence,
sensor alignment and that the correct part variant was loaded.

## Material supply
ASSY-01 needs housings, screws and seals from the logistics area. Waiting for material is a
loss for OEE (organisational stop) even if the cell is technically fine. Typical causes:
missing kanban cards, late replenishment at shift start, and weekend stock not refilled
before the Monday early shift.

## Preventive maintenance plan
**Daily (operator):** light curtain test with test rod, clean lenses, check screw feeder level.
**Weekly (maintenance, about 60 min):** check screwdriver bit and torque with test joint, check
pneumatic connections, check turntable index accuracy, inspect cables in the cable chain.
**Monthly:** calibrate leak tester, check light curtain response time.
