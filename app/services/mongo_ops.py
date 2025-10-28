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


async def create_job(total: int, document_ids: List[str], user_id: Optional[str] = None) -> str:
    db = get_db()
    job = {
        "status": "pending",  # pending|running|done|error
        "progress": {"current": 0, "total": total},
        "document_ids": [ObjectId(x) for x in document_ids],
        "user_id": user_id,
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
) -> None:
    """Append a log entry to the job_logs collection for the given job."""
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
    if extra:
        try:
            # Avoid nesting very large data; shallow copy
            entry["extra"] = dict(extra)
        except Exception:
            entry["extra"] = {"note": "unserializable extra"}
    await db["job_logs"].insert_one(entry)


async def list_job_logs(job_id: str, *, limit: int = 200, since: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
    """List recent job logs ordered by timestamp ascending."""
    db = get_db()
    q: Dict[str, Any] = {"job_id": job_id}
    if since is not None:
        q["ts"] = {"$gte": since}
    cur = db["job_logs"].find(q).sort("ts", 1).limit(limit)
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
    try:
        from pymongo import ReturnDocument  # type: ignore
    except Exception:
        # Fallback: return without promotion if pymongo isn't available for sort/return options
        return None
    job = await db["jobs"].find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "running", "started_at": now, "updated_at": now}},
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    return job


async def list_pending_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db["jobs"].find({"status": "pending"}).sort("created_at", 1).limit(limit)
    return await cur.to_list(length=limit)
