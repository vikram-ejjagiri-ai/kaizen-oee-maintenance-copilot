from datetime import date

import pytest

from src import copilot, oee
from src.retrieval import Retriever, build_chunks, tokenize


@pytest.fixture(scope="module")
def bot(tables):
    t = tables
    f = oee.shift_facts(t)
    return copilot.Copilot(t, f, Retriever(build_chunks(t["work_orders"])), use_llm=False)


def test_tokenizer_keeps_alarm_codes():
    assert "a-217" in tokenize("What does alarm A-217 mean?")


@pytest.mark.parametrize("q,start,end", [
    ("OEE last week", date(2026, 8, 17), date(2026, 8, 23)),
    ("OEE in week 31", date(2026, 7, 27), date(2026, 8, 2)),
    ("scrap in July", date(2026, 7, 1), date(2026, 7, 31)),
    ("what happened on 30 July", date(2026, 7, 30), date(2026, 7, 30)),
])
def test_period_parsing(q, start, end):
    p = copilot.parse_period(q, today=date(2026, 8, 29))
    assert (p.start, p.end) == (start, end)


def test_machine_parsing():
    assert copilot.parse_machines("is cnc 2 ok?") == ["CNC-02"]
    assert copilot.parse_machines("the press and the assembly cell") == ["PRESS-01", "ASSY-01"]


@pytest.mark.parametrize("q", ["How do I bypass the light curtain?", "can I bridge the door interlock",
                               "disable the two-hand control"])
def test_safety_guardrail(bot, q):
    a = bot.ask(q)
    assert a.mode == "Guardrail (safety)"
    assert a.sources[0][0].doc_id == "SOP-LOTO"


def test_out_of_scope(bot):
    assert bot.ask("What is the capital of France?").mode == "Not found"


def test_kpi_numbers_come_from_engine(bot):
    a = bot.ask("What was the OEE of CNC-02 last week?")
    f = oee.filter_facts(bot.facts, "2026-08-17", "2026-08-23", ["CNC-02"])
    expected = f"OEE {100 * oee.aggregate(f).oee.iloc[0]:.1f} %"
    assert any(expected in line for line in a.kpi["lines"])


def test_last_time_returns_newest_fix(bot):
    a = bot.ask("What fixed the light curtain fault on ASSY-01 last time?")
    wos = [c for c, _ in a.sources if c.source_type == "work_order"]
    assert "receiver cable" in wos[0].text


def test_answer_check_flags_invented_numbers():
    flags = copilot.check_answer("OEE was 91.3 % [KPI]", "OEE 58.0 % (availability 82.1 %)")
    assert flags and flags[0].startswith("unverified_numbers")
    assert copilot.check_answer("OEE was 58.0 % [KPI]", "OEE 58.0 %") == []


def test_llm_path_with_fake_ollama(bot, monkeypatch):
    """The LLM path, tested without Ollama: a fake server returns a fixed answer."""
    class Fake:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "OEE was 58.0 % because the spindle bearing failed [KPI] [S1]."}}

    monkeypatch.setattr(copilot.requests, "post", lambda *a, **k: Fake())
    bot.llm = "fake-model"
    try:
        a = bot.ask("Why was OEE low on CNC-02 at the end of July?")
    finally:
        bot.llm = None
    assert a.mode.startswith("LLM")
    assert "no_citations" not in a.flags
    assert not any(f.startswith("unverified_numbers") for f in a.flags)


def test_dense_and_hybrid_search_run_with_fake_embedder(tables, tmp_path, monkeypatch):
    """Dense search without Ollama: a fake embedder (hashed bag of words) stands in."""
    import numpy as np

    from src import config

    class FakeEmbedder:
        model = "fake"

        def embed(self, texts):
            v = np.zeros((len(texts), 256), dtype=np.float32)
            for i, t in enumerate(texts):
                for tok in tokenize(t):
                    v[i, hash(tok) % 256] += 1
            return v / np.linalg.norm(v, axis=1, keepdims=True).clip(1e-9)

    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    r = Retriever(build_chunks(tables["work_orders"]), FakeEmbedder())
    assert r.has_dense
    for method in ("dense", "hybrid"):
        hits = r.search("What does alarm A-217 mean?", k=3, method=method, types={"manual", "sop"})
        assert len(hits) == 3
    assert list(tmp_path.glob("embeddings_*.npy"))      # cached for the next start


def test_search_survives_embedding_server_errors(tables, tmp_path, monkeypatch):
    """If Ollama fails on a query (e.g. HTTP 500, out of memory), search falls back to BM25."""
    import numpy as np
    import requests

    from src import config

    class FlakyEmbedder:
        model = "flaky"
        calls = 0

        def embed(self, texts):
            FlakyEmbedder.calls += 1
            if FlakyEmbedder.calls > 1:          # documents OK, then every query fails
                raise requests.HTTPError("500 Server Error")
            v = np.ones((len(texts), 8), dtype=np.float32)
            return v / np.linalg.norm(v, axis=1, keepdims=True)

    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    r = Retriever(build_chunks(tables["work_orders"]), FlakyEmbedder())
    hits = r.search("What does alarm A-217 mean?", k=1, method="hybrid", types={"manual", "sop"})
    assert hits[0][0].chunk_id == "MAN-TL400#alarm-a-217-spindle-vibration-high"
    assert r.dense_failures == 1
