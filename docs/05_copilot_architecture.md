# 05 – Copilot Architecture

Code: `src/copilot.py`, `src/retrieval.py` · Knowledge: `knowledge/`

```
question
   |
   v
[1 Guardrail] -- bypass a safety device? --> refuse + point to SOP-LOTO + safe troubleshooting
   |
[2 Understand] machines (CNC-02, "the press"), alarm codes (A-217), period ("last week",
   |           "week 31", "end of July"), shift, intent (KPI? documents? history?)
   v
[3 Tools]
   KPI tool ............ OEE engine on MES data (numbers are CALCULATED)
   Document search ..... manuals + SOPs (BM25 / embeddings / hybrid)
   History search ...... work orders (newest first for "last time")
   |
[4 Answer] local LLM (Ollama) writes from facts + numbered sources, cites [KPI] [S1] ...
   |        no Ollama -> fallback: facts + best passages, same sources
   v
[5 Checks] every number in the answer must appear in the facts; citations required
```

## Why this design (and not "just ask ChatGPT")
- **LLMs are bad at arithmetic and make up numbers.** All KPIs come from the OEE engine.
  The LLM only explains them. Step 5 flags any number not found in the facts.
- **RAG (retrieval-augmented generation):** the LLM answers from retrieved plant documents,
  not from its training data, and must cite them. A technician can open the source.
- **Tool use:** the question decides which tools run. "Why was OEE low on CNC-02 at the
  end of July?" runs the KPI tool first, then uses the biggest downtime reasons and alarms
  of that period (spindle failure, A-217) as extra search words. The numbers steer the search.
- **Local:** Ollama runs the LLM on the plant PC or the laptop GPU (RTX 4060: qwen2.5 7B
  answers in a few seconds). Nothing leaves the plant.

## Retrieval details
- **Chunking:** one chunk per manual section (`## heading`), with the document title added
  so each chunk stands alone. One chunk per work order.
- **Two lanes:** documents and work orders are searched separately. There are about 155
  work orders and 37 document sections; in one combined search the many similar work
  orders push the manual sections out of the top results.
- **BM25:** keyword search; excellent for codes like A-217 or SB-7014 (the tokenizer keeps
  them as one token). Weak for paraphrases ("the press gets too warm").
- **Plant glossary:** a small, versioned list that maps shop-floor words to manual words
  (overheat -> temperature, shakes -> vibration). Cheap, transparent, but needs maintenance.
- **Dense embeddings** (`nomic-embed-text` via Ollama): match meaning, not words.
- **Hybrid:** BM25 and dense rankings fused with Reciprocal Rank Fusion (RRF, k = 60).
- **Machine filter:** "CNC-02" restricts to documents for that machine plus plant-wide SOPs.
- **Recency:** for "last time" questions, the most relevant work orders are sorted newest first.

## Guardrails
- **Safety:** requests to bypass, bridge, mute or disable light curtains, interlocks,
  e-stops or two-hand controls are refused before any LLM call. The answer cites the
  LOTO SOP and offers the real troubleshooting steps instead.
- **Out of scope / low confidence:** if no KPI is asked and the best search score is below
  a threshold, the copilot says it did not find it rather than guessing.
- **Repair answers** always end with the lockout/tagout reminder.

## Limits
- The question parser is rule-based (regex). It is predictable and testable, but misses
  unusual phrasing. An LLM-based parser (function calling) is the next step.
- The copilot does not create work orders or change anything. Read-only by design.
