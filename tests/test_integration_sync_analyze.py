"""
Integration-style test for synchronous PDF analysis using a real PDF from example_papers.
This test exercises the AgentRunner directly (no API or Mongo required).

Note: Requires Ollama with the embedding model available and a reachable LLM endpoint.
Mark as 'integration' so it can be skipped by default in pure unit runs.
"""
import os
import pytest

from app.services.agent import AgentRunner
from app.core.errors import EmbeddingModelMissingError, LLMServiceError, InvalidPDFError


@pytest.mark.integration
def test_sync_analyze_real_pdf():
    # Pick a realistic paper from example_papers
    base = os.path.dirname(os.path.dirname(__file__))
    pdf_path = os.path.join(base, "example_papers", "agostini2021.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip("Example PDF not present")

    runner = AgentRunner()
    try:
        result = runner.analyze(pdf_path)
    except EmbeddingModelMissingError:
        pytest.skip("Embedding model missing in local environment")
    except LLMServiceError:
        pytest.skip("LLM service not available in test environment")
    except ImportError as e:
        pytest.skip(f"Optional embedding dependency missing: {e}")

    # Basic sanity checks: not asserting specific content (papers vary), but structure should be present
    assert result is not None
    # It’s okay if title/doi are None, but links and statements should be lists/strings or None
    assert isinstance(result.data_links, list)
    assert isinstance(result.code_links, list)
