from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel

from app.services.db import get_db


class MongoId(str):
    @classmethod
    def from_obj(cls, v: Any) -> "MongoId":
        return cls(str(v))


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def create_document(*, filename: str, content_type: str, size: int, sha256: str, gridfs_id: str, job_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
    db = get_db()
    doc = {
        "filename": filename,
        "content_type": content_type,
        "size": size,
        "sha256": sha256,
        "gridfs_id": gridfs_id,
        "status": "uploaded",  # uploaded|queued|processing|done|error
        "job_id": job_id,
        "user_id": user_id,
        "error": None,
        "analysis": None,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    res = await db["documents"].insert_one(doc)
    return str(res.inserted_id)


async def set_document_status(doc_id: str, status: str, error: Optional[str] = None) -> None:
    db = get_db()
    await db["documents"].update_one({"_id": ObjectId(doc_id)}, {"$set": {"status": status, "error": error, "updated_at": now_utc()}})


async def set_document_analysis(doc_id: str, analysis: Dict[str, Any]) -> None:
    db = get_db()
    await db["documents"].update_one({"_id": ObjectId(doc_id)}, {"$set": {"analysis": analysis, "updated_at": now_utc(), "status": "done"}})


async def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db["documents"].find_one({"_id": ObjectId(doc_id)})

async def get_document_for_user(doc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db["documents"].find_one({"_id": ObjectId(doc_id), "user_id": user_id})


async def create_job(total: int, document_ids: List[str], user_id: Optional[str] = None, user_email: Optional[str] = None) -> str:
    db = get_db()
    job = {
        "status": "pending",  # pending|running|done|error
        "progress": {"current": 0, "total": total},
        "document_ids": [ObjectId(x) for x in document_ids],
        "user_id": user_id,
        "user_email": user_email,
        "error": None,
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "started_at": None,
        "finished_at": None,
    }
    res = await db["jobs"].insert_one(job)
    return str(res.inserted_id)


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db["jobs"].find_one({"_id": ObjectId(job_id)})

async def get_job_for_user(job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db["jobs"].find_one({"_id": ObjectId(job_id), "user_id": user_id})


async def inc_job_progress(job_id: str, by: int = 1) -> None:
    db = get_db()
    await db["jobs"].update_one({"_id": ObjectId(job_id)}, {"$inc": {"progress.current": by}, "$set": {"updated_at": now_utc()}})


async def set_job_status(job_id: str, status: str, error: Optional[str] = None) -> None:
    db = get_db()
    now = now_utc()
    update: Dict[str, Any] = {"status": status, "error": error, "updated_at": now}
    if status == "running":
        update["started_at"] = now
    if status in {"done", "error"}:
        update["finished_at"] = now
    await db["jobs"].update_one({"_id": ObjectId(job_id)}, {"$set": update})


async def list_job_documents(job_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db["documents"].find({"job_id": job_id})
    return await cur.to_list(length=10000)

async def list_user_jobs(user_id: str, limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {"user_id": user_id}
    if status:
        q["status"] = status
    cur = db["jobs"].find(q).sort("created_at", -1).limit(limit)
    return await cur.to_list(length=limit)

async def list_all_jobs(limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    cur = db["jobs"].find(q).sort("created_at", -1).limit(limit)
    return await cur.to_list(length=limit)


async def set_document_job_id(doc_id: str, job_id: str) -> None:
    db = get_db()
    await db["documents"].update_one({"_id": ObjectId(doc_id)}, {"$set": {"job_id": job_id, "updated_at": now_utc()}})


# --- Job logs ---
async def append_job_log(
    job_id: str,
    *,
    level: str = "info",
    op: Optional[str] = None,
    message: Optional[str] = None,
    doc_id: Optional[str] = None,
    filename: Optional[str] = None,
    duration_ms: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
    ts: Optional[dt.datetime] = None,
    phase: Optional[str] = None,
    progress_current: Optional[int] = None,
    progress_total: Optional[int] = None,
    percent: Optional[int] = None,
    worker: Optional[str] = None,
) -> None:
    """Append a log entry to the job_logs collection for the given job.

    Added verbose optional fields: phase, progress snapshot, percent, worker identifier.
    """
    db = get_db()
    entry: Dict[str, Any] = {
        "job_id": job_id,
        "ts": ts or now_utc(),
        "level": level,
    }
    if op:
        entry["op"] = op
    if message:
        entry["message"] = message
    if doc_id:
        entry["doc_id"] = doc_id
    if filename:
        entry["filename"] = filename
    if duration_ms is not None:
        entry["duration_ms"] = int(duration_ms)
    if phase:
        entry["phase"] = phase
    if progress_current is not None:
        entry["progress_current"] = int(progress_current)
    if progress_total is not None:
        entry["progress_total"] = int(progress_total)
    if percent is not None:
        entry["percent"] = int(percent)
    if worker:
        entry["worker"] = worker
    if extra:
        try:
            entry["extra"] = dict(extra)
        except Exception:
            entry["extra"] = {"note": "unserializable extra"}
    await db["job_logs"].insert_one(entry)


async def list_job_logs(
    job_id: str,
    *,
    limit: int = 200,
    since: Optional[dt.datetime] = None,
    order: str = "asc",
    since_id: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """List job logs with ordering.

    order: 'asc' for oldest->newest (default), 'desc' for newest first.
    """
    db = get_db()
    q: Dict[str, Any] = {"job_id": job_id}
    sort_dir = -1 if str(order).lower() == "desc" else 1
    since_oid: Optional[ObjectId] = None
    if since_id is not None:
        if isinstance(since_id, ObjectId):
            since_oid = since_id
        else:
            try:
                since_oid = ObjectId(str(since_id))
            except Exception:
                since_oid = None

    if since is not None and since_oid is not None:
        if sort_dir == 1:
            q["$or"] = [
                {"ts": {"$gt": since}},
                {"ts": since, "_id": {"$gt": since_oid}},
            ]
        else:
            q["$or"] = [
                {"ts": {"$lt": since}},
                {"ts": since, "_id": {"$lt": since_oid}},
            ]
    elif since is not None:
        op = "$gte" if sort_dir == 1 else "$lte"
        q["ts"] = {op: since}
    elif since_oid is not None:
        op = "$gt" if sort_dir == 1 else "$lt"
        q["_id"] = {op: since_oid}

    cur = db["job_logs"].find(q).sort("ts", sort_dir).limit(limit)
    return await cur.to_list(length=limit)


# --- Job dispatching helpers ---
async def get_running_job() -> Optional[Dict[str, Any]]:
    """Return the currently running job if any."""
    db = get_db()
    return await db["jobs"].find_one({"status": "running"})


async def promote_next_pending_job() -> Optional[Dict[str, Any]]:
    """Promote the oldest pending job to running if none is running.

    Returns the promoted job document, or None if no promotion occurred.
    """
    db = get_db()
    # If a job is already running, do nothing
    existing = await db["jobs"].find_one({"status": "running"})
    if existing:
        return None

    now = now_utc()
    # Preferred fast path using ReturnDocument
    try:
        from pymongo import ReturnDocument  # type: ignore
        job = await db["jobs"].find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "running", "started_at": now, "updated_at": now}},
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return job
    except Exception:
        # Manual fallback path if pymongo isn't available for sort/return options
        cur = db["jobs"].find({"status": "pending"}).sort("created_at", 1).limit(1)
        candidates = await cur.to_list(length=1)
        if not candidates:
            return None
        j = candidates[0]
        j_id = j.get("_id")
        res = await db["jobs"].update_one(
            {"_id": j_id, "status": "pending"},
            {"$set": {"status": "running", "started_at": now, "updated_at": now}},
        )
        if getattr(res, "modified_count", 0) == 1:
            # Successfully claimed; return the updated job
            try:
                updated = await db["jobs"].find_one({"_id": j_id})
                return updated
            except Exception:
                # If find_one by _id is not supported by the stub, return local doc
                j["status"] = "running"
                j["started_at"] = now
                j["updated_at"] = now
                return j
        # Lost the race; treat as no promotion
        return None


async def list_pending_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db["jobs"].find({"status": "pending"}).sort("created_at", 1).limit(limit)
    return await cur.to_list(length=limit)
