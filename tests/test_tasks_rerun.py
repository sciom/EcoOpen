import sys
import types
import pytest
from typing import Any


def _patch_no_mongo(monkeypatch):
    # Disable Mongo-backed lifespan to avoid real connection attempts
    monkeypatch.setattr("app.main._MONGO_ENABLED", False, raising=False)


def _install_fake_mongo_ops(monkeypatch, *, get_job_returns=None, list_job_logs_returns=None):
    mod = types.ModuleType("app.services.mongo_ops")

    async def get_job(job_id: str):  # type: ignore
        return get_job_returns

    async def get_job_for_user(job_id: str, user_id: str):  # type: ignore
        return get_job_returns

    async def create_job(total: int, document_ids: list, user_id: str, user_email: str):  # type: ignore
        return "new_job_id_12345"

    async def create_document(*, filename: str, content_type: str, size: int, sha256: str, gridfs_id: str, job_id: str, user_id: str):  # type: ignore
        return f"new_doc_id_{hash(filename) % 1000}"

    async def list_job_documents(job_id: str):  # type: ignore
        return [
            {
                "_id": "doc1",
                "filename": "test1.pdf",
                "content_type": "application/pdf",
                "size": 1000,
                "sha256": "abc123",
                "gridfs_id": "gridfs123"
            },
            {
                "_id": "doc2", 
                "filename": "test2.pdf",
                "content_type": "application/pdf",
                "size": 2000,
                "sha256": "def456",
                "gridfs_id": "gridfs456"
            }
        ]

    mod.get_job = get_job  # type: ignore
    mod.get_job_for_user = get_job_for_user  # type: ignore
    mod.create_job = create_job  # type: ignore
    mod.create_document = create_document  # type: ignore
    mod.list_job_documents = list_job_documents  # type: ignore
    sys.modules["app.services.mongo_ops"] = mod


def _install_fake_db(monkeypatch):
    mod = types.ModuleType("app.services.db")

    async def get_db():  # type: ignore
        return FakeDB()

    mod.get_db = get_db  # type: ignore
    sys.modules["app.services.db"] = mod


class FakeDB:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class FakeCollection:
    def __init__(self):
        self.items = []

    async def update_many(self, filter_dict, update_dict):
        return {"acknowledged": True, "modified_count": 1}


def _make_token(email: str, sub: str = "u1") -> str:
    from app.core.config import settings
    from jose import jwt

    payload = {"sub": sub, "email": email}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.mark.asyncio
async def test_rerun_task_success(client, monkeypatch):
    """Test successful job rerun creates new job"""
    _patch_no_mongo(monkeypatch)
    
    # Mock job data
    fake_job = {
        "_id": "test_job_id",
        "status": "done",
        "user_id": "u1"
    }
    
    _install_fake_mongo_ops(monkeypatch, get_job_returns=fake_job)
    _install_fake_db(monkeypatch)
    
    token = _make_token("user@example.com", "u1")
    
    r = client.post("/tasks/test_job_id/rerun", headers={"Authorization": f"Bearer {token}"})
    
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["job_id"] == "new_job_id_12345"  # New job ID
    assert data["status"] == "queued"
    assert data["original_job_id"] == "test_job_id"  # Original job ID tracked


@pytest.mark.asyncio
async def test_rerun_task_not_found(client, monkeypatch):
    """Test rerun with non-existent job"""
    _patch_no_mongo(monkeypatch)
    
    _install_fake_mongo_ops(monkeypatch, get_job_returns=None)
    _install_fake_db(monkeypatch)
    
    token = _make_token("user@example.com", "u1")
    
    r = client.post("/tasks/does_not_exist/rerun", headers={"Authorization": f"Bearer {token}"})
    
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_rerun_task_wrong_status(client, monkeypatch):
    """Test rerun with job that has wrong status"""
    _patch_no_mongo(monkeypatch)
    
    # Mock job with running status (should not be rerunnable)
    fake_job = {
        "_id": "test_job_id",
        "status": "running",
        "user_id": "u1"
    }
    
    _install_fake_mongo_ops(monkeypatch, get_job_returns=fake_job)
    _install_fake_db(monkeypatch)
    
    token = _make_token("user@example.com", "u1")
    
    r = client.post("/tasks/test_job_id/rerun", headers={"Authorization": f"Bearer {token}"})
    
    assert r.status_code == 400
    assert "Can only rerun completed or failed jobs" in r.json()["detail"]


@pytest.mark.asyncio
async def test_rerun_task_unauthorized(client, monkeypatch):
    """Test rerun without authentication"""
    _patch_no_mongo(monkeypatch)
    
    r = client.post("/tasks/test_job_id/rerun")
    
    assert r.status_code == 401