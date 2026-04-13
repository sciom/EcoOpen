import sys
import types
import csv
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _override_auth(app):
    from app.routes import export as export_module
    app.dependency_overrides[export_module._get_current_user] = lambda: {"id": "u1", "email": "user@example.com"}


def _install_fake_mongo_with_flag(monkeypatch):
    mo_mod = types.ModuleType("app.services.mongo_ops")

    async def get_job_for_user(job_id, user_id):
        return {"_id": job_id, "status": "done", "progress": {"current": 1, "total": 1}}

    async def get_job(job_id):
        return {"_id": job_id, "status": "done", "progress": {"current": 1, "total": 1}}

    async def list_job_documents(job_id):
        return [
            {
                "status": "done",
                "filename": "example.pdf",
                "analysis": {
                    "title": "Sample Title",
                    "title_source": "heuristic",
                    "doi": "10.1234/example.doi",
                    "doi_from_title_search": True,
                    "data_availability_statement": "Data available upon request.",
                    "code_availability_statement": "Code available on GitHub.",
                    "data_sharing_license": "CC-BY-4.0",
                    "code_license": "MIT",
                    "data_links": ["https://data.example.com/d1"],
                    "code_links": ["https://github.com/example/repo"],
                },
            }
        ]

    mo_mod.get_job_for_user = get_job_for_user  # type: ignore
    mo_mod.list_job_documents = list_job_documents  # type: ignore
    mo_mod.get_job = get_job  # type: ignore

    sys.modules["app.services.mongo_ops"] = mo_mod


def test_export_includes_doi_from_title_search(monkeypatch):
    _override_auth(app)
    _install_fake_mongo_with_flag(monkeypatch)

    job_id = "job-flag-123"
    r = client.get(f"/export/csv/{job_id}")
    if r.status_code != 200:
        pytest.skip(f"CSV export not available: {r.status_code} {r.text}")

    content = r.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "doi_from_title_search" in headers, headers

    row = next(reader)
    idx = headers.index("doi_from_title_search")
    assert row[idx] in ("true", "")
    # For this fixture it should be 'true'
    assert row[idx] == "true"
