import datetime as dt
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
