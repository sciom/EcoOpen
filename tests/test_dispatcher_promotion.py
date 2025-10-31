import datetime as dt
import builtins as _builtins
import pytest


class _FakeJobs:
    def __init__(self):
        t0 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
        self._jobs = [
            {"_id": "j1", "status": "pending", "created_at": t0, "updated_at": t0, "started_at": None, "finished_at": None, "progress": {"current": 0, "total": 2}},
            {"_id": "j2", "status": "pending", "created_at": t0 + dt.timedelta(seconds=10), "updated_at": t0 + dt.timedelta(seconds=10), "started_at": None, "finished_at": None, "progress": {"current": 0, "total": 1}},
        ]

    async def find_one(self, query):
        # Only support {"status": "running"}
        status = query.get("status")
        if status == "running":
            for j in self._jobs:
                if j.get("status") == "running":
                    return j
        return None

    async def find_one_and_update(self, query, update, sort=None, return_document=None):
        # Promote oldest pending job to running
        status = query.get("status")
        if status != "pending":
            return None
        # sort by created_at ascending
        pending = [j for j in self._jobs if j.get("status") == "pending"]
        if not pending:
            return None
        pending.sort(key=lambda j: j["created_at"])
        job = pending[0]
        now = dt.datetime.now(dt.timezone.utc)
        job["status"] = "running"
        job["started_at"] = now
        job["updated_at"] = now
        return job

    # Helpers for the test to mutate state
    def mark_done(self, job_id: str):
        for j in self._jobs:
            if j["_id"] == job_id:
                j["status"] = "done"
                j["finished_at"] = dt.datetime.now(dt.timezone.utc)
                j["updated_at"] = j["finished_at"]


class _FakeDB:
    def __init__(self, jobs: _FakeJobs):
        self._jobs = jobs

    def __getitem__(self, name: str):
        assert name == "jobs"
        return self._jobs


@pytest.mark.skipif(__import__("importlib").util.find_spec("pymongo") is None, reason="pymongo not installed")
@pytest.mark.asyncio
async def test_promote_next_pending_job_ordering(monkeypatch):
    from app.services import mongo_ops

    fake_jobs = _FakeJobs()
    fake_db = _FakeDB(fake_jobs)

    def fake_get_db():
        return fake_db

    monkeypatch.setattr(mongo_ops, "get_db", fake_get_db, raising=False)

    # Initially, no running job; promote should pick j1 (oldest)
    promoted = await mongo_ops.promote_next_pending_job()
    assert promoted is not None
    assert promoted.get("_id") == "j1"
    running = await mongo_ops.get_running_job()
    assert running is not None and running.get("_id") == "j1"

    # With a running job, second promotion should no-op
    promoted2 = await mongo_ops.promote_next_pending_job()
    assert promoted2 is None

    # Mark current running job as done; next promotion should pick j2
    fake_jobs.mark_done("j1")
    promoted3 = await mongo_ops.promote_next_pending_job()
    assert promoted3 is not None
    assert promoted3.get("_id") == "j2"


# --- Fallback path test (when pymongo import fails) ---
class _FakeJobsFallback:
    def __init__(self):
        t0 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
        self._jobs = [
            {"_id": "f1", "status": "pending", "created_at": t0, "updated_at": t0, "started_at": None, "finished_at": None, "progress": {"current": 0, "total": 2}},
            {"_id": "f2", "status": "pending", "created_at": t0 + dt.timedelta(seconds=10), "updated_at": t0 + dt.timedelta(seconds=10), "started_at": None, "finished_at": None, "progress": {"current": 0, "total": 1}},
        ]

    async def find_one(self, query):
        if query.get("status") == "running":
            for j in self._jobs:
                if j.get("status") == "running":
                    return j
        if query.get("_id"):
            for j in self._jobs:
                if j.get("_id") == query.get("_id"):
                    return j
        return None

    class _Cursor:
        def __init__(self, jobs):
            self._jobs = jobs

        def sort(self, field, order):
            reverse = order == -1 or (isinstance(order, tuple) and len(order) > 1 and order[1] == -1)
            self._jobs = sorted(self._jobs, key=lambda j: j[field], reverse=reverse)
            return self

        def limit(self, n):
            self._jobs = self._jobs[:n]
            return self

        async def to_list(self, length):
            return self._jobs[:length]

    def find(self, query):
        if query.get("status") == "pending":
            pending = [j for j in self._jobs if j.get("status") == "pending"]
            return self._Cursor(pending)
        return self._Cursor([])

    async def update_one(self, filt, update):
        target_id = filt.get("_id")
        status = filt.get("status")
        modified = 0
        for j in self._jobs:
            if j["_id"] == target_id and j.get("status") == status:
                now = dt.datetime.now(dt.timezone.utc)
                j["status"] = "running"
                j["started_at"] = now
                j["updated_at"] = now
                modified = 1
                break

        class _Res:
            modified_count = modified
        return _Res()

    def mark_done(self, job_id: str):
        for j in self._jobs:
            if j["_id"] == job_id:
                j["status"] = "done"
                j["finished_at"] = dt.datetime.now(dt.timezone.utc)
                j["updated_at"] = j["finished_at"]


class _FakeDBFallback:
    def __init__(self, jobs):
        self._jobs = jobs

    def __getitem__(self, name: str):
        assert name == "jobs"
        return self._jobs


@pytest.mark.asyncio
async def test_promote_next_pending_job_manual_fallback(monkeypatch):
    # Force pymongo import to fail inside promote_next_pending_job
    real_import = _builtins.__import__

    def _raising_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-redef]
        if name == "pymongo" or (name == "pymongo" and fromlist):
            raise ImportError("simulated missing pymongo")
        return real_import(name, globals, locals, fromlist, level)  # type: ignore[misc]

    monkeypatch.setattr(_builtins, "__import__", _raising_import)

    from app.services import mongo_ops

    fake_jobs = _FakeJobsFallback()
    fake_db = _FakeDBFallback(fake_jobs)

    def fake_get_db():
        return fake_db

    monkeypatch.setattr(mongo_ops, "get_db", fake_get_db, raising=False)

    # No running job; fallback should promote f1 (oldest pending)
    promoted = await mongo_ops.promote_next_pending_job()
    assert promoted is not None
    assert promoted.get("_id") == "f1"

    # With a running job, promotion should no-op
    promoted2 = await mongo_ops.promote_next_pending_job()
    assert promoted2 is None

    # After marking f1 done, next promotion should pick f2
    fake_jobs.mark_done("f1")
    promoted3 = await mongo_ops.promote_next_pending_job()
    assert promoted3 is not None
    assert promoted3.get("_id") == "f2"
