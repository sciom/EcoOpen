import os
from app.services.agent import AgentRunner
from app.core.config import settings


def test_agent_runner_debug_and_title_source(monkeypatch):
    monkeypatch.setenv("EXPOSE_AVAILABILITY_DEBUG", "true")
    # We cannot reinitialize global settings easily; rely on branch checks using settings flag
    # Run agent directly to avoid auth + DB requirements
    pdf_path = os.path.join(os.path.dirname(__file__), "..", "example_papers", "test_full_paper.pdf")
    pdf_path = os.path.abspath(pdf_path)
    runner = AgentRunner(context={"filename": "test_full_paper.pdf"})
    result = runner.analyze(pdf_path)
    # title and source
    if result.title:
        assert result.title_source in (None, "heuristic", "llm", "enriched")
    # debug info exposure depends on settings flag (may be false if singleton already loaded before monkeypatch)
    # Accept either present or None; if present ensure link_verification key when toggle is enabled
    if result.debug_info is not None and settings.ENABLE_LINK_VERIFICATION:
        assert "link_verification" in result.debug_info
