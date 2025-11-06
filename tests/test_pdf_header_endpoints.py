import types
import sys
import pytest


def _install_fake_mongo_modules(monkeypatch):
    # Create fake app.services.db with put_file
    db_mod = types.ModuleType("app.services.db")

    async def put_file(content: bytes, filename: str, content_type: str, metadata: dict) -> str:
        return "gridfs-id-1"

    db_mod.put_file = put_file  # type: ignore

    # Create fake app.services.mongo_ops with required functions
    mo_mod = types.ModuleType("app.services.mongo_ops")

    async def create_document(**kwargs):
        return "doc-1"

    async def create_job(**kwargs):
        return "job-1"

    async def set_document_job_id(doc_id, job_id):
        return None

    async def set_document_status(doc_id, status):
        return None

    mo_mod.create_document = create_document  # type: ignore
    mo_mod.create_job = create_job  # type: ignore
    mo_mod.set_document_job_id = set_document_job_id  # type: ignore
    mo_mod.set_document_status = set_document_status  # type: ignore

    sys.modules["app.services.db"] = db_mod
    sys.modules["app.services.mongo_ops"] = mo_mod


def _override_auth(app):
    from app.routes import analyze as analyze_module
    app.dependency_overrides[analyze_module._get_required_user] = lambda: {"id": "u1", "email": "user@example.com"}


def test_single_analyze_rejects_non_pdf(client):
    # Override auth to bypass JWT dependency
    from app.main import app as fastapi_app
    _override_auth(fastapi_app)

    files = {"file": ("not.pdf", b"NOT A PDF", "application/pdf")}
    r = client.post("/analyze?mode=sync", files=files)
    assert r.status_code == 400
    assert "bad header" in r.text


def test_batch_analyze_rejects_non_pdf(client, monkeypatch):
    from app.main import app as fastapi_app
    _override_auth(fastapi_app)

    _install_fake_mongo_modules(monkeypatch)
    files = [("files", ("bad.pdf", b"BAD!!", "application/pdf"))]
    r = client.post("/analyze/batch", files=files)
    assert r.status_code == 400
    assert "not a valid PDF" in r.text or "bad header" in r.text
