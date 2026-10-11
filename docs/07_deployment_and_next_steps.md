# 07 – Deployment and Next Steps

## How it would run in a plant
```
MES / SCADA ──> events, counts ──┐
CMMS ─────────> work orders ─────┼──> PostgreSQL ──> OEE engine ──> dashboard (Streamlit / Power BI)
PLC alarms ───> OPC UA / MQTT ───┘                         │
Manuals, SOPs (PDF) ──> chunker ──> search index ──────────┴──> copilot (Ollama on a plant server)
```
- Everything on-premise: one server with a mid-range GPU runs Ollama for 20-50 users.
- Read-only access to MES and CMMS databases (a reporting user, never write access).
- Nightly job: refresh facts, re-index new work orders and changed documents.
- Log every copilot question and answer (with sources) for review; this is also the source
  of new evaluation questions.

## Organisational points (often more important than the code)
- **Works council (Betriebsrat):** OEE per shift can be read as performance monitoring of
  people. Agree up front: OEE is used to improve machines and processes, not to rate
  individuals. Shift-level, not person-level data.
- **Data quality ownership:** someone must own reason codes and the corrections list.
- **Safety:** the copilot is an assistant. Approved SOPs and qualified people stay in charge.

## Next steps (good extensions for your own commits)
1. **Connect to the Kaizen factory stack (project 1):** publish machine states to MQTT,
   store them in PostgreSQL, and read `events` from there instead of the simulation.
2. **PDF ingestion:** real manuals are PDFs; add a PDF-to-text step (e.g. `pypdf`) before chunking.
3. **LLM question parser:** replace the regex parser with Ollama function calling and
   compare both on the evaluation set.
4. **Predictive link:** feed the A-217 alarm trend into an alert ("CNC-02 vibration warnings
   doubled this week"), the way project 2 predicts failures.
5. **Work order assistant:** draft a structured work order from the technician's notes.
6. **Docker:** package app + Ollama with docker-compose for one-command deployment.
