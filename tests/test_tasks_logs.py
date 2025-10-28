import pytest
from typing import Any


def _patch_no_mongo(monkeypatch):
    # Disable Mongo-backed lifespan to avoid real connection attempts
    monkeypatch.setattr("app.main._MONGO_ENABLED", False, raising=False)


def _make_token(email: str, sub: str = "u1") -> str:
    from app.core.config import settings
    from jose import jwt

    payload = {"sub": sub, "email": email}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)  # type: ignore


def test_logs_requires_admin_403(client, monkeypatch):
    _patch_no_mongo(monkeypatch)

    # Non-admin email by default (settings.ADMIN_EMAILS empty)
    token = _make_token("user@example.com")

    r = client.get("/tasks/abc123/logs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert "Admin access required" in r.text


@pytest.mark.asyncio
async def test_logs_unknown_job_404(client, monkeypatch):
    _patch_no_mongo(monkeypatch)

    # Make this user an admin
    from app.core.config import settings
    admin_email = "admin@example.com"
    settings.ADMIN_EMAILS = [admin_email]

    # Patch mongo_ops.get_job to return None
    async def _fake_get_job(job_id: str) -> Any:
        return None

    monkeypatch.setattr("app.services.mongo_ops.get_job", _fake_get_job, raising=False)

    token = _make_token(admin_email)
    r = client.get("/tasks/does-not-exist/logs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
    assert "Job not found" in r.text


def test_logs_import_failure_503(client, monkeypatch):
    _patch_no_mongo(monkeypatch)

    # Make this user an admin
    from app.core.config import settings
    admin_email = "admin@example.com"
    settings.ADMIN_EMAILS = [admin_email]

    import builtins as _builtins

    real_import = _builtins.__import__

    def _raising_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-redef]
        # Intentionally fail only when importing app.services.mongo_ops inside the handler
        if name == "app.services.mongo_ops" or (name == "app.services" and fromlist and "mongo_ops" in fromlist):
            raise ImportError("simulated missing mongo deps")
        return real_import(name, globals, locals, fromlist, level)  # type: ignore[misc]

    monkeypatch.setattr(_builtins, "__import__", _raising_import)

    token = _make_token(admin_email)
    r = client.get("/tasks/any/logs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503
    assert "Logs require Mongo dependencies" in r.text
