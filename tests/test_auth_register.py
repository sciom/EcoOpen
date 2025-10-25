import pytest
from typing import Any


class _FakeInsertResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id


class _FakeUsers:
    def __init__(self, existing_email: str | None = None):
        self._existing_email = (existing_email or '').lower()

    async def find_one(self, query):
        email = (query.get('email') or '').lower()
        if self._existing_email and email == self._existing_email:
            return {"_id": "existing-id", "email": email, "password_hash": "hash"}
        return None

    async def insert_one(self, doc):
        return _FakeInsertResult(inserted_id="abc123")


class _FakeDB:
    def __init__(self, existing_email: str | None = None):
        self._users = _FakeUsers(existing_email=existing_email)

    def __getitem__(self, name: str):
        assert name == "users"
        return self._users


def _patch_no_mongo(monkeypatch):
    # Disable Mongo-backed lifespan to avoid real connection attempts
    monkeypatch.setattr("app.main._MONGO_ENABLED", False, raising=False)


def _patch_get_db(monkeypatch, existing_email: str | None = None):
    def fake_get_db():
        return _FakeDB(existing_email=existing_email)
    monkeypatch.setattr("app.services.db.get_db", fake_get_db, raising=False)


def test_register_success(client, monkeypatch):
    _patch_no_mongo(monkeypatch)
    _patch_get_db(monkeypatch)

    payload = {"email": "user@example.com", "password": "Abcdef12", "password_confirm": "Abcdef12"}
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == "user@example.com"
    assert "id" in data and data["id"]
    assert "created_at" in data and data["created_at"]


def test_register_mismatch_passwords(client, monkeypatch):
    _patch_no_mongo(monkeypatch)
    # No DB patch needed since it fails before DB access

    payload = {"email": "user@example.com", "password": "Abcdef12", "password_confirm": "WRONG"}
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 400
    assert "do not match" in r.text


def test_register_weak_password(client, monkeypatch):
    _patch_no_mongo(monkeypatch)
    # Weak: too short / missing digit or letter
    payload = {"email": "user@example.com", "password": "short1", "password_confirm": "short1"}
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 400
    assert "at least 8 characters" in r.text or "include letters and numbers" in r.text
