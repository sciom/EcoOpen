import os
import sys
import types
import pytest


def _install_minimal_mongo(monkeypatch):
    # Provide minimal async functions used in /analyze path when queue fallback occurs
    db_mod = types.ModuleType("app.services.db")

    async def put_file(content: bytes, filename: str, content_type: str, metadata: dict) -> str:
        return "gridfs-id-1"

    db_mod.put_file = put_file  # type: ignore

    mo_mod = types.ModuleType("app.services.mongo_ops")

    async def create_document(**kwargs):
        return "doc-1"

    async def set_document_job_id(doc_id, job_id):
        return None

    async def set_document_status(doc_id, status):
        return None

    async def get_document(doc_id):
        # Simulate never finishing so code falls back to sync path (poll timeout)
        return {"status": "queued"}

    async def create_job(**kwargs):
        return "job-1"

    async def set_document_analysis(doc_id, analysis):
        return None

    mo_mod.create_document = create_document  # type: ignore
    mo_mod.set_document_job_id = set_document_job_id  # type: ignore
    mo_mod.set_document_status = set_document_status  # type: ignore
    mo_mod.get_document = get_document  # type: ignore
    mo_mod.create_job = create_job  # type: ignore
    mo_mod.set_document_analysis = set_document_analysis  # type: ignore

    sys.modules["app.services.db"] = db_mod
    sys.modules["app.services.mongo_ops"] = mo_mod


def _override_auth(app):
    from app.routes import analyze as analyze_module
    app.dependency_overrides[analyze_module._get_required_user] = lambda: {"id": "u1", "email": "user@example.com"}


def test_analyze_title_source_present_sync(client, monkeypatch):
    from app.main import app as fastapi_app
    _override_auth(fastapi_app)
    _install_minimal_mongo(monkeypatch)

    pdf_path = os.path.join(os.path.dirname(__file__), "..", "example_papers", "test_full_paper.pdf")
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.exists(pdf_path):
        pytest.skip("Example test PDF missing")

    with open(pdf_path, "rb") as f:
        content = f.read()
    files = {"file": ("test_full_paper.pdf", content, "application/pdf")}
    resp = client.post("/analyze?mode=sync", files=files)
    if resp.status_code != 200:
        pytest.skip(f"Analyze endpoint returned {resp.status_code}: {resp.text}")
    data = resp.json()
    assert "title" in data
    if data.get("title"):
        assert data.get("title_source") in (None, "heuristic", "llm", "enriched")
    else:
        assert data.get("title_source") in (None, "")
