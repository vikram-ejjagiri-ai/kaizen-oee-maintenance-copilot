# 06 – Evaluation

Code: `src/evaluate.py` · Questions: `eval/questions.jsonl` · Results: `reports/results.md`,
`reports/eval_answers.csv`

A copilot demo that answers three hand-picked questions proves nothing. This project
measures it like a product.

## Question set (49 questions)
| Type | Count | What "pass" means |
|---|---|---|
| alarm | 10 | the manual section for that alarm is among the sources |
| procedure | 10 | the right procedure / SOP section is among the sources |
| paraphrase | 10 | right source although the question uses different words ("the lathe shakes") |
| history | 6 | the right work order is among the sources ("what fixed it last time") |
| safety | 4 | the request to bypass a safety device is refused |
| out_of_scope | 4 | "not found" instead of a made-up answer |
| kpi | 5 | period parsed correctly AND OEE, availability and scrap rate equal an independent calculation |

## Metrics
- **Hit@k:** share of questions where a correct source is in the top k results.
- **MRR (mean reciprocal rank):** 1 if the correct source is first, 1/2 if second, ... averaged.
- **End-to-end pass rate:** per type, as in the table above.
- **LLM answers (if Ollama runs):** share with citations, share where every number is found
  in the facts, median latency.

## How to read the results
- BM25 is perfect on alarm codes and procedures, weaker on paraphrases: exactly the gap
  dense embeddings close. Run with Ollama and compare the `bm25` and `hybrid` rows.
- Failed questions are listed in the report on purpose. A 100 % score on your own test set
  usually means the test set is too easy.

## Honest limitation: this is a development set
The questions were written while building the copilot, so the system is tuned to them.
For a fair number, write 20 new questions **without looking at the code**, add them to
`eval/questions.jsonl` with a new id prefix, and report that score separately (see the
learning guide). In a real plant, collect real questions from technicians for two weeks.
