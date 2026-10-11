# 01 – Problem Definition

## Situation
A small metal-parts plant runs four machines in three shifts: two CNC turning centers
(CNC-01, CNC-02), a hydraulic press (PRESS-01) and a semi-automated assembly cell (ASSY-01).
The MES (manufacturing execution system) records every stop with a reason code and the part
counts per shift. The CMMS (maintenance software) holds the work orders. The machine manuals
and SOPs are PDF files on a shared drive.

## The two problems
**1. Nobody sees the losses.** The plant manager hears "we were busy all week" but output is
below plan. Shift reports exist, but nobody adds up where the time goes. Typical questions
that take a day of Excel work today:
- What is our OEE per machine, and is it getting better or worse?
- What are the biggest losses: breakdowns, changeovers, waiting, slow running, scrap?
- Is one shift different from the others?

**2. Knowledge is scattered.** A technician on the night shift with alarm A-217 has to search
a 40-page manual, and the knowledge "what fixed this last time" sits in old work orders that
nobody reads. Experienced technicians retire and take that knowledge with them.

## Goal
One tool with two parts:
1. **OEE dashboard:** OEE, availability, performance and quality per machine, shift and week,
   loss waterfall, downtime Pareto, MTBF/MTTR. Numbers people can trust (data checks).
2. **Maintenance copilot:** answers questions in plain language from the plant data, manuals,
   SOPs and work order history, **with sources**, and never makes up numbers.

## Users
| User | Typical question |
|---|---|
| Plant / production manager | "Which machine lost the most time last month, and why?" |
| Shift leader | "Why was OEE low on CNC-02 at the end of July?" |
| Maintenance technician | "What does H-104 mean, what should I check, what fixed it last time?" |
| Maintenance planner | "Which failures repeat? What should go into the PM plan?" |

## Success criteria
- OEE numbers match an independent calculation exactly (tested).
- Data problems are detected and fixed transparently, never silently.
- Copilot finds the right source for at least 80 % of realistic questions, refuses unsafe
  requests 100 %, says "not found" instead of guessing, and cites sources.
- Runs **on-premise**: no plant data leaves the factory (local LLM via Ollama). In Germany
  this matters for data protection and for the works council (Betriebsrat), who must agree
  to systems that process employee-related data.

## Constraints and honest limits
- The data is **simulated** (real MES data is confidential). The simulation contains planted
  stories so we can check that the tools find them (see `src/simulate.py`).
- Manuals, SOPs and machines are fictional and written for this project.
