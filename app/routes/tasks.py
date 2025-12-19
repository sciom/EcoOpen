from __future__ import annotations

from typing import Any, List, Optional

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId

from app.core.config import settings
from app.models.schemas import JobLogEntryModel, BatchStatusModel, BatchProgress, PDFAnalysisResultModel

router = APIRouter(prefix="/tasks")

logger = logging.getLogger(__name__)

_security = HTTPBearer(auto_error=False)


def _is_admin(user: dict) -> bool:
    try:
        email = (user.get("email") or "").strip().lower()
    except Exception:
        return False
    return email in (settings.ADMIN_EMAILS or [])


async def _get_required_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security)) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        from jose import jwt, JWTError  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Auth requires python-jose (install dependencies).")
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        sub = str(payload.get("sub") or "").strip()
        email = str(payload.get("email") or "").strip()
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": sub, "email": email}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/", summary="List recent tasks (jobs)")
async def list_tasks(
    status: Optional[str] = Query(default=None, description="Filter by status: pending|running|done|error"),
    limit: int = Query(default=100, ge=1, le=1000),
    user: dict = Depends(_get_required_user),
):
    try:
        from app.services.mongo_ops import list_user_jobs, list_all_jobs  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Listing tasks requires Mongo dependencies (motor/pymongo).")

    rows = await (list_all_jobs(limit=limit, status=status) if _is_admin(user) else list_user_jobs(user_id=user["id"], limit=limit, status=status))

    def map_row(j: dict) -> dict:
        jid = str(j.get("_id"))
        created_at = j.get("created_at")
        updated_at = j.get("updated_at")
        started_at = j.get("started_at")
        finished_at = j.get("finished_at")
        dur_ms = None
        try:
            if started_at and finished_at:
                dur_ms = int((finished_at - started_at).total_seconds() * 1000)
        except Exception:
            dur_ms = None
        row = {
            "job_id": jid,
            "status": j.get("status"),
            "progress": j.get("progress") or {"current": 0, "total": 0},
            "user_id": j.get("user_id"),
            "error": j.get("error"),
            "created_at": created_at,
            "updated_at": updated_at,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": dur_ms,
        }
        # Include creator info for admins to aid triage
        try:
            if _is_admin(user):
                row["created_by"] = {
                    "user_id": j.get("user_id"),
                    "email": j.get("user_email"),
                }
        except Exception:
            pass
        return row

    return [map_row(j) for j in rows]


@router.get("/{job_id}", response_model=BatchStatusModel)
async def get_task_detail(job_id: str, user: dict = Depends(_get_required_user)):
    try:
        from app.services.mongo_ops import (
            get_job_for_user,
            list_job_documents,
            get_job,
            set_job_status,
            append_job_log,
        )  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Job status requires Mongo dependencies (motor/pymongo).")

    job = await (get_job(job_id) if _is_admin(user) else get_job_for_user(job_id, user["id"]))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    docs = await list_job_documents(job_id)
    results: List[PDFAnalysisResultModel] = []
    for d in docs:
        if d.get("status") == "done" and d.get("analysis"):
            try:
                r = PDFAnalysisResultModel(**(d.get("analysis") or {}))
                r.source_file = d.get("filename") or "unknown.pdf"
                results.append(r)
            except Exception:
                # Fallback minimal result if shape invalid
                results.append(PDFAnalysisResultModel(source_file=d.get("filename") or "unknown.pdf"))
        elif d.get("status") == "error" and d.get("error"):
            results.append(PDFAnalysisResultModel(source_file=d.get("filename") or "unknown.pdf", error=d.get("error")))

    progress = job.get("progress") or {"current": 0, "total": len(docs)}
    status = job.get("status") or "pending"

    # Auto-finalize if all docs are terminal but job still pending/running
    try:
        if status in {"pending", "running"}:
            remaining = [d for d in docs if d.get("status") in {"queued", "processing", "uploaded"}]
            if not remaining:
                await set_job_status(job_id, "done")
                try:
                    await append_job_log(job_id, op="job_done", phase="job", message="Job finalized in status endpoint")
                except Exception:
                    pass
                status = "done"
    except Exception:
        pass

    dur_ms = None
    try:
        started_at = job.get("started_at")
        finished_at = job.get("finished_at")
        if started_at and finished_at:
            dur_ms = int((finished_at - started_at).total_seconds() * 1000)
    except Exception:
        dur_ms = None

    return BatchStatusModel(
        job_id=job_id,
        status=status,
        progress=BatchProgress(current=progress.get("current", 0), total=progress.get("total", len(docs))),
        results=results,
        error=job.get("error"),
        duration_ms=dur_ms,
    )


@router.post("/{job_id}/cancel")
async def cancel_task(job_id: str, user: dict = Depends(_get_required_user)):
    try:
        from app.services.mongo_ops import get_job_for_user, get_job, set_job_status  # type: ignore
        from app.services.db import get_db  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Cancel requires Mongo dependencies (motor/pymongo).")

    job = await (get_job(job_id) if _is_admin(user) else get_job_for_user(job_id, user["id"]))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await set_job_status(job_id, "error", error="Cancelled by user")

    db = get_db()
    try:
        await db["documents"].update_many({"job_id": job_id, "status": {"$in": ["queued", "processing", "uploaded"]}}, {"$set": {"status": "error", "error": "Cancelled by user"}})
    except Exception:
        pass

    return {"ok": True, "job_id": job_id, "status": "error"}


@router.post("/{job_id}/rerun")
async def rerun_task(job_id: str, user: dict = Depends(_get_required_user)):
    try:
        from app.services.mongo_ops import get_job_for_user, get_job, list_job_documents, create_job, create_document  # type: ignore
        from app.services.db import get_db  # type: ignore
        from bson import ObjectId
    except Exception:
        raise HTTPException(status_code=503, detail="Rerun requires Mongo dependencies (motor/pymongo).")

    job = await (get_job(job_id) if _is_admin(user) else get_job_for_user(job_id, user["id"]))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only allow rerunning completed or failed jobs
    if job.get("status") not in ["done", "error"]:
        raise HTTPException(status_code=400, detail="Can only rerun completed or failed jobs")

    # Get all documents from the original job
    documents = await list_job_documents(job_id)
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found in job")

    # Create a new job
    new_job_id = await create_job(
        total=len(documents),
        document_ids=[],  # Will be populated as we create documents
        user_id=user["id"],
        user_email=user["email"]
    )

    # Create new documents for the new job, copying file data from originals
    db = get_db()
    new_document_ids = []
    
    for doc in documents:
        try:
            # Copy the document data but create fresh document for new job
            gridfs_id = doc.get("gridfs_id")
            if not gridfs_id:
                logger.warning(f"Document {doc.get('_id')} has no gridfs_id, skipping")
                continue
                
            new_doc_id = await create_document(
                filename=doc.get("filename", "unknown.pdf"),
                content_type=doc.get("content_type", "application/pdf"),
                size=doc.get("size", 0),
                sha256=doc.get("sha256", ""),
                gridfs_id=gridfs_id,  # Reuse same GridFS file
                job_id=new_job_id,
                user_id=user["id"]
            )
            new_document_ids.append(new_doc_id)
        except Exception as e:
            # Log error but continue with other documents
            logger.warning(f"Failed to copy document {doc.get('_id')} for rerun: {e}")

    # Update the new job with the document IDs
    try:
        await db["jobs"].update_one(
            {"_id": ObjectId(new_job_id)},
            {"$set": {"document_ids": new_document_ids}}
        )
    except Exception:
        pass

    return {"ok": True, "job_id": new_job_id, "status": "queued", "original_job_id": job_id}


@router.post("/{job_id}/delete")
async def delete_task(job_id: str, user: dict = Depends(_get_required_user)):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        from app.services.db import get_db, get_fs  # type: ignore
        from bson import ObjectId  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Delete requires Mongo dependencies (motor/pymongo).")

    db = get_db()
    fs = get_fs()

    # Delete associated documents and GridFS files (best-effort)
    docs = await db["documents"].find({"job_id": job_id}).to_list(length=10000)
    for d in docs:
        gid = d.get("gridfs_id")
        if gid:
            try:
                oid = ObjectId(gid)
                await fs.delete(oid)
            except Exception:
                # Ignore failures deleting files
                pass
    await db["documents"].delete_many({"job_id": job_id})
    await db["jobs"].delete_one({"_id": ObjectId(job_id)})

    return {"ok": True, "job_id": job_id, "deleted": True}


@router.get("/{job_id}/logs", response_model=List[JobLogEntryModel])
async def get_job_logs(
    job_id: str,
    limit: int = Query(default=200, ge=1, le=2000),
    since: Optional[str] = Query(default=None, description="ISO8601 timestamp to filter logs since this time"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    user: dict = Depends(_get_required_user),
):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Defer Mongo imports to handler to allow app startup without Mongo deps
    try:
        from app.services.mongo_ops import list_job_logs, get_job  # type: ignore
        import datetime as dt  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Logs require Mongo dependencies (motor/pymongo).")

    # Optional existence check to return clearer 404s
    job = await get_job(job_id)
    if not job:
        logger.info("logs endpoint: job not found for id=%s", job_id)
        raise HTTPException(status_code=404, detail="Job not found")

    since_dt: Optional[dt.datetime] = None
    if since:
        try:
            # Parse flexible ISO8601
            since_dt = dt.datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                # Assume UTC if naive
                since_dt = since_dt.replace(tzinfo=dt.timezone.utc)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid 'since' timestamp format; use ISO8601")

    rows = await list_job_logs(job_id, limit=limit, since=since_dt, order=order)
    logger.debug("logs endpoint: returning %d rows for job=%s", len(rows or []), job_id)

    # Pydantic will coerce dicts into JobLogEntryModel via response_model
    return rows


@router.get("/{job_id}/logs/download")
async def download_job_logs(
    job_id: str,
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    user: dict = Depends(_get_required_user),
):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        from app.services.mongo_ops import list_job_logs, get_job  # type: ignore
        import datetime as dt  # type: ignore
        import json  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Logs require Mongo dependencies (motor/pymongo).")

    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Preflight: if no logs at all, return a small NDJSON body directly
    preview = await list_job_logs(job_id, limit=1, since=None, order=order)
    if not preview:
        filename = f"job_{job_id}_logs.ndjson"
        headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
        body = json.dumps({"job_id": job_id, "info": "no logs available"}) + "\n"
        return Response(content=body, media_type="application/x-ndjson", headers=headers)

    async def stream_ndjson():
        # Stream in chunks to avoid memory blowups
        batch_size = 1000
        since_dt: Optional[dt.datetime] = None
        since_id: Optional[Any] = None
        yielded_any = False
        while True:
            rows = await list_job_logs(job_id, limit=batch_size, since=since_dt, order=order, since_id=since_id)
            if not rows:
                break
            for row in rows:
                # Ensure JSON-serializable; let FastAPI handle datetime encoding by converting to iso
                try:
                    doc = dict(row)
                    if doc.get("ts"):
                        try:
                            doc["ts"] = doc["ts"].isoformat()
                        except Exception:
                            doc["ts"] = str(doc["ts"])  # fallback
                    yielded_any = True
                    yield (json.dumps(doc) + "\n").encode("utf-8")
                except Exception:
                    # Best-effort continue
                    continue
            # Advance since_dt for ascending only; for desc, paging by since isn't ideal so we stop after first chunk
            if order == "asc":
                try:
                    last = rows[-1]
                    since_id = last.get("_id")
                    ts = last.get("ts")
                    if ts is not None:
                        if isinstance(ts, str):
                            try:
                                since_dt = dt.datetime.fromisoformat(ts)
                            except Exception:
                                since_dt = None
                        else:
                            since_dt = ts
                    else:
                        since_dt = None
                except Exception:
                    since_dt = None
                    since_id = None
            else:
                break
        if not yielded_any:
            try:
                placeholder = {"job_id": job_id, "info": "no logs available"}
                yield (json.dumps(placeholder) + "\n").encode("utf-8")
            except Exception:
                # Last resort to avoid empty body
                yield b'{"info":"no logs available"}\n'

    filename = f"job_{job_id}_logs.ndjson"
    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return StreamingResponse(stream_ndjson(), media_type="application/x-ndjson", headers=headers)
