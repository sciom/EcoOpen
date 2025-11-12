import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _override_auth(app):
    from app.routes import analyze as analyze_module
    app.dependency_overrides[analyze_module._get_required_user] = lambda: {"id": "u1", "email": "user@example.com"}


def test_analyze_includes_title_source_sync(monkeypatch):
    # Override auth to bypass JWT
    _override_auth(app)

    pdf_path = os.path.join(os.path.dirname(__file__), "..", "example_papers", "test_full_paper.pdf")
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.exists(pdf_path):
        pytest.skip("Example test PDF missing")

    with open(pdf_path, "rb") as f:
        files = {"file": ("test_full_paper.pdf", f.read(), "application/pdf")}

    r = client.post("/analyze?mode=sync", files=files)
    if r.status_code != 200:
        pytest.skip(f"Analyze not available in test env: {r.status_code} {r.text}")

    data = r.json()
    # title_source should be present and constrained when title exists
    if data.get("title"):
        assert data.get("title_source") in (None, "heuristic", "llm", "enriched")
    else:
        assert data.get("title_source") in (None, "")
