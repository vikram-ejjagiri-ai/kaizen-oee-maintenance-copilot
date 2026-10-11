"""Central settings. Change things here, not inside the code."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
EVAL_DIR = ROOT / "eval"

# ---- Simulated plant -------------------------------------------------------
SEED = 7
START_DATE = date(2026, 6, 1)    # a Monday
END_DATE = date(2026, 8, 30)     # a Sunday -> 13 full weeks
# "Today" for the copilot. Questions like "last week" are relative to this date.
AS_OF_DATE = date(2026, 8, 29)   # a Saturday, the day after the last production day

# Shift name -> start hour. Each shift is 8 hours. Production Monday to Friday.
SHIFTS = {"Early": 6, "Late": 14, "Night": 22}
SHIFT_MINUTES = 480

# ---- Copilot --------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("KAIZEN_LLM_MODEL", "qwen2.5:7b")
EMBED_MODEL = os.getenv("KAIZEN_EMBED_MODEL", "nomic-embed-text")
TOP_K = 4                         # how many text chunks the copilot reads
MIN_BM25_SCORE = 4.0              # below this, retrieval is "not confident"
LLM_TIMEOUT_S = 120
