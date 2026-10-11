# Learning Guide

Work through the stages in order. For each one, read the doc, open the code it points to, then answer the questions without looking. The answers are hidden below each block. Plan for about 2 days.

---

## Setup and first run (do this first)
1. Follow the README, step 1 (no Ollama yet). Open `reports/results.md`.
2. Start the app and click through all three tabs. Try the example questions.
3. Install Ollama (README step 2), run the pipeline again, and compare the copilot answers and the retrieval table with fallback mode.

---

## Stage 1: Problem and data
**Read:** `docs/01_problem_definition.md`, `docs/02_data_model.md`. **Code:** `src/simulate.py` (skim it).

1. What is the difference between MES and CMMS data?
2. Why does every shift have to add up to exactly 480 minutes of events?
3. Why are performance losses not booked as stop reasons?
4. Why simulate data with "planted stories"?

<details><summary>Answers</summary>

1. MES records production: machine states, stop reasons and part counts. CMMS records maintenance: work orders with symptom, cause, action and parts.
2. Each minute belongs to exactly one state. Gaps or overlaps mean lost or double-counted time, so the OEE would be wrong.
3. Short stops (under 2 minutes) and slow running are not booked by operators. They are calculated from counts and ideal cycle times.
4. You know the truth, so you can test whether the dashboard and the copilot find it, the same way unit tests check code.
</details>

---

## Stage 2: OEE engine and checks
**Read:** `docs/03_oee_engine.md`. **Code:** `src/oee.py`, `src/checks.py`, `tests/test_oee.py`.

1. Calculate it by hand: PPT 420 min, 35 min downtime, ideal cycle 30 s, 700 parts, 14 scrap. What are A, P, Q and OEE?
2. Why is averaging shift OEE percentages wrong?
3. A shift shows 126 % performance. What do you check first?
4. Why are corrections written in `KNOWN_CORRECTIONS` instead of just fixed in the CSV?

<details><summary>Answers</summary>

1. Run time = 385 min, so A = 91.7 %. Ideal time = 700 × 30 s = 350 min, so P = 90.9 %. Q = 686/700 = 98.0 %. OEE = 686 × 0.5 min / 420 min = 81.7 %.
2. A short or partly idle shift gets the same weight as a full shift. Sum the minutes first, then divide.
3. The product booked and its ideal cycle time. Usually the wrong product was booked, or the master data is wrong.
4. Traceability. Everyone can see what was changed, why, and who confirmed it. Silent fixes destroy trust in the KPI.
</details>

---

## Stage 3: Dashboard
**Read:** `docs/04_dashboard.md`. **Code:** `app/app.py`.

1. The waterfall shows that speed loss and minor stops are bigger than all breakdowns together. What would you do differently because of that?
2. Why does each machine always keep the same colour?
3. The night shift on the press has longer die changes. Is that a people problem?

<details><summary>Answers</summary>

1. Look at cycle times and short stops (observe the machine, log short stops, check speed settings), not only at breakdowns.
2. So that people recognise a machine across charts and filters. A colour based on rank would change when the filter changes.
3. Usually not. It is typically missing preparation or support (crane driver, die cart, setup team) at night. That is SMED and organisation. This is also why OEE data is not used to rate individuals.
</details>

---

## Stage 4: Copilot
**Read:** `docs/05_copilot_architecture.md`. **Code:** `src/retrieval.py`, `src/copilot.py`.

1. Why does the LLM never calculate the KPIs?
2. Why are documents and work orders searched in separate "lanes"?
3. BM25 or embeddings: which one is better for "A-217", and which one for "the lathe shakes"?
4. How does the copilot find the right work order for "what fixed it last time"?
5. Why is the safety check done before the LLM is called?
6. What does "the numbers steer the search" mean in the CNC-02 example?

<details><summary>Answers</summary>

1. LLMs make arithmetic mistakes and invent plausible-looking numbers. The OEE engine calculates the numbers; the LLM only explains them, and a check flags any number that is not in the facts.
2. There are about 155 similar work orders and only 37 document sections. In one combined search the work orders crowd out the manual sections.
3. BM25 for exact codes. Embeddings for paraphrases, because they match meaning rather than words.
4. It retrieves many relevant work orders, keeps the ones close to the best score, and sorts them newest first.
5. A refusal must not depend on the LLM behaving well. A rule that runs first is predictable and testable.
6. The KPI tool finds the biggest losses of the period (spindle failure, A-217 alarms) and adds them as search words, so the search finds the bearing work orders.
</details>

---

## Stage 5: Evaluation
**Read:** `docs/06_evaluation.md`. **Look at:** `reports/results.md`, `reports/eval_answers.csv`.

1. What does Hit@3 = 89 % mean?
2. Why are the failed questions shown in the report?
3. Why is the score on this question set probably too optimistic?

<details><summary>Answers</summary>

1. For 89 % of the questions, a correct source was in the top 3 search results.
2. Honesty, and because they show the next improvement (paraphrases point to embeddings).
3. The questions were written while the system was being built and tuned (a development set). Unseen questions usually score lower.
</details>

---

## Your own commits (real work, real learning)
These extensions are yours. Each one makes a good commit with your own message:
1. **Held-out evaluation:** write 20 new questions without looking at the code (ids `H01`–`H20`) and report their score separately.
2. **Compare models:** run the evaluation with `qwen2.5:7b` and `llama3.2:3b`. Compare quality and latency.
3. **New alarm:** add an alarm to a manual (e.g. A-412 axis overtravel) plus 3 questions, and check that the copilot finds it.
4. **Connect project 1:** send machine states over MQTT to PostgreSQL and read `events` from there.

---

## Your 60-second pitch (fill in your numbers from reports/results.md)
> "I built an OEE dashboard and a maintenance copilot for a simulated metal-parts plant. The OEE engine follows ISO 22400 and has data checks that caught duplicate MES records and a wrong product booking. The dashboard showed that plant OEE was ___ %, that the biggest losses were speed loss and changeovers, and that night-shift die changes on the press took ___ minutes instead of ___. The copilot answers questions from the MES data, manuals and work orders. It runs locally with Ollama, takes all numbers from the OEE engine, cites its sources and refuses unsafe requests. On a 49-question evaluation it passed ___ %, including all safety and KPI questions. For example, it explains that CNC-02's OEE drop in July came from a spindle bearing failure that had been announced by vibration alarms three weeks earlier."
