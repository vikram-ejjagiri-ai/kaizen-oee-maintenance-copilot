# Portfolio update

The numbers below come from `python -m src.pipeline --no-llm`. The simulation uses a fixed seed, so your run produces exactly the same numbers. Check them against your own `reports/results.md`. After you run the pipeline with Ollama, update the evaluation line with your hybrid and LLM results.

Add this card to `src/data/projects.js` after `visual-quality-inspection`, then renumber the later projects (05, 06, ...).

```js
  {
    id: "oee-maintenance-copilot",
    number: "04",
    title: "OEE Dashboard + Maintenance Copilot",
    shortTitle: "OEE + Copilot",
    category: "Industrial AI",
    tags: ["OEE", "LLM / RAG", "Manufacturing Analytics"],
    description:
      "An OEE dashboard that shows where production time is lost, and an on-premise maintenance copilot that answers shop-floor questions from MES data, manuals and work orders, with sources.",
    objective:
      "Make losses visible per machine, shift and week, and give technicians fast, cited answers about alarms, procedures and past repairs, without sending plant data to the cloud.",
    achievements: [
      "Built an ISO 22400 OEE engine with data checks that caught duplicate MES records and a wrong product booking; KPI numbers are verified against an independent calculation.",
      "Dashboard revealed a plant OEE of 76.8 %, speed loss and changeovers as the biggest losses, and night-shift die changes taking 73 min instead of 40 min.",
      "Built a RAG copilot with tool use: the OEE engine supplies all numbers, hybrid search (BM25 + embeddings) finds manual sections and work orders, and a local LLM (Ollama) answers with citations.",
      "Added guardrails: refuses to explain how to bypass safety devices, says 'not found' instead of guessing, and flags any number not traceable to the data.",
      "Evaluated on 49 questions: 93.9 % end-to-end pass rate in keyword-only mode, including 100 % on safety, out-of-scope and KPI questions."
    ],
    tools: ["Python", "pandas", "Streamlit", "Plotly", "Ollama", "RAG", "Pytest"],
    visual: "sensor",
    image: "projects/oee-maintenance-copilot.png",
    github: "https://github.com/vikram-ejjagiri-ai/kaizen-oee-maintenance-copilot"
  },
```

Card image (PowerShell, from the project folder):
```
Copy-Item reports\figures\app_dashboard.png ~\Desktop\portfolio\public\projects\oee-maintenance-copilot.png
```
Then commit **both** the image and `projects.js` in the portfolio folder.
