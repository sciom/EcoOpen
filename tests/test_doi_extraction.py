import os
import types
import pytest

from app.services.agent import AgentRunner
from app.services.text_normalizer import ParagraphBlock
from app.core.config import settings


class _StubVS:
    def similarity_search(self, q, k=4):
        return []


def _blocks(texts):
    out = []
    for i, t in enumerate(texts):
        out.append(ParagraphBlock(text=t, page=1, column=0, seq=i))
    return out


def _patch_minimal(monkeypatch, blocks):
    monkeypatch.setattr(AgentRunner, "_load_pdf_blocks", lambda self, path: blocks, raising=False)
    monkeypatch.setattr(AgentRunner, "_vector_store", lambda self, chunks: _StubVS(), raising=False)
    # Prevent actual LLM calls
    monkeypatch.setattr(AgentRunner, "_chat", lambda self, sys, user: "", raising=False)


def test_doi_front_matter_harvest(monkeypatch, tmp_path):
    blocks = _blocks([
        "Deep Learning for Ecology",
        "doi:10.1234/example.2025.001",
        "Authors: ...",
    ])
    _patch_minimal(monkeypatch, blocks)
    # Keep verification off for this front-matter harvest check
    monkeypatch.setattr(settings, "ENABLE_DOI_VERIFICATION", False, raising=False)
    runner = AgentRunner()

    # Provide a dummy file path (not used due to patch)
    pdf_path = os.path.join(tmp_path, "dummy.pdf")
    result = runner.analyze(pdf_path)

    assert result.doi == "10.1234/example.2025.001"
    assert result.confidence_scores.get("doi", 0) >= 0.9


def test_doi_llm_hallucination_guard(monkeypatch, tmp_path):
    blocks = _blocks([
        "A Paper Without DOI",
        "Abstract",
    ])
    _patch_minimal(monkeypatch, blocks)

    # Force LLM to suggest a DOI not present in text
    monkeypatch.setattr(AgentRunner, "_similarity_context_multi", lambda self, vs, q, k_each=4, max_chars=4000: "context", raising=False)
    monkeypatch.setattr(AgentRunner, "_chat", lambda self, sys, user: "10.9999/hallucinated", raising=False)

    runner = AgentRunner()
    pdf_path = os.path.join(tmp_path, "dummy.pdf")
    result = runner.analyze(pdf_path)

    assert result.doi in (None, "")


def test_doi_verification_boost(monkeypatch, tmp_path):
    # Enable verification via settings singleton
    monkeypatch.setattr(settings, "ENABLE_DOI_VERIFICATION", True, raising=False)

    blocks = _blocks([
        "Sample Ecological Study",
        "https://doi.org/10.5678/verify.match",
    ])
    _patch_minimal(monkeypatch, blocks)

    # Stub registry to return matching title
    from app.services import doi_registry as mod

    class _FakeReg(mod.DOIRegistry):
        def __init__(self):
            pass
        def lookup(self, doi: str):
            return {"title": "Sample Ecological Study"}

    monkeypatch.setattr(mod, "DOIRegistry", _FakeReg, raising=False)

    runner = AgentRunner()
    pdf_path = os.path.join(tmp_path, "dummy.pdf")
    result = runner.analyze(pdf_path)

    assert result.doi == "10.5678/verify.match"
    # Confidence should be > base due to verification boost; at least 1.0 cap acceptable
    assert result.confidence_scores.get("doi", 0.0) >= 0.6


def test_doi_multicandidate_prefix_boost_and_debug(monkeypatch, tmp_path):
    # Show debug to inspect scored candidates
    monkeypatch.setattr(settings, "EXPOSE_AVAILABILITY_DEBUG", True, raising=False)

    blocks = _blocks([
        "Complex Study Title",
        "Early mention 10.2222/seconddoi",
        "Published version doi:10.1111/chosen.doi",
    ])
    _patch_minimal(monkeypatch, blocks)

    runner = AgentRunner()
    pdf_path = os.path.join(tmp_path, "dummy.pdf")
    result = runner.analyze(pdf_path)

    assert result.doi == "10.1111/chosen.doi"
    dbg = result.debug_info or {}
    doi_dbg = (dbg.get("doi_debug") if isinstance(dbg, dict) else None) or {}
    scored = doi_dbg.get("scored") or []
    # First scored candidate should be the chosen with higher score due to 'doi:' prefix boost
    assert isinstance(scored, list) and scored
    assert scored[0].get("value") == "10.1111/chosen.doi"


def test_doi_verification_negative_reduces_confidence(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ENABLE_DOI_VERIFICATION", True, raising=False)

    blocks = _blocks([
        "Unrelated Title",
        "doi:10.3333/notfound",
    ])
    _patch_minimal(monkeypatch, blocks)

    # Force registry to return None (e.g., Crossref non-200)
    from app.services import doi_registry as mod

    class _NoneReg(mod.DOIRegistry):
        def __init__(self):
            pass
        def lookup(self, doi: str):
            return None

    monkeypatch.setattr(mod, "DOIRegistry", _NoneReg, raising=False)

    runner = AgentRunner()
    pdf_path = os.path.join(tmp_path, "dummy.pdf")
    result = runner.analyze(pdf_path)

    assert result.doi == "10.3333/notfound"
    # Base would be high from 'doi:' context; verification failure should reduce it
    conf = result.confidence_scores.get("doi", 0.0)
    assert 0.3 <= conf <= 0.8


def test_doi_registry_caching_and_ttl(monkeypatch):
    from app.services import doi_registry as mod

    calls = {"count": 0}

    class _FakeResp:
        status_code = 200
        def __init__(self, title):
            self._title = title
            self.text = ""
        def json(self):
            return {
                "message": {
                    "title": [self._title],
                    "container-title": ["Journal"],
                    "issued": {"date-parts": [[2024]]},
                }
            }

    class _FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def get(self, url, headers=None):
            calls["count"] += 1
            return _FakeResp(title="Cached Title")

    # Monkeypatch httpx.Client used in DOIRegistry
    monkeypatch.setattr(mod.httpx, "Client", _FakeClient, raising=False)

    # Control time progression
    base = 1000.0
    monkeypatch.setattr(mod.time, "time", lambda: base, raising=False)

    reg = mod.DOIRegistry(timeout_sec=2, cache_ttl=1)
    rec1 = reg.lookup("10.4242/cached")
    assert rec1 and rec1.get("title") == "Cached Title"
    assert calls["count"] == 1

    # Second lookup should be cached
    rec2 = reg.lookup("10.4242/cached")
    assert rec2 and rec2.get("title") == "Cached Title"
    assert calls["count"] == 1

    # Advance time beyond TTL to force re-fetch
    monkeypatch.setattr(mod.time, "time", lambda: base + 2, raising=False)
    rec3 = reg.lookup("10.4242/cached")
    assert rec3 and rec3.get("title") == "Cached Title"
    assert calls["count"] == 2
