from __future__ import annotations

from typing import List, Optional
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.models.schemas import BatchStatusModel, BatchProgress, PDFAnalysisResultModel
from app.routes.auth import get_current_user

router = APIRouter(prefix="/tasks")

def _is_admin(user: dict) -> bool:
    try:
        email = (user.get("email") or "").strip().lower()
    except Exception:
        return False
    return email in (settings.ADMIN_EMAILS or [])


def _iso(d: object) -> Optional[str]:
    if isinstance(d, (dt.datetime,)):
        try:
            return d.isoformat()
        except Exception:
            return None
    return None


@router.get("/", response_model=List[BatchStatusModel])
async def list_tasks(status: Optional[str] = Query(default=None, pattern="^(pending|running|done|error)$"), limit: int = Query(default=100, ge=1, le=500), user=Depends(get_current_user)):
    try:
        from app.services.mongo_ops import list_user_jobs, list_all_jobs  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Tasks require Mongo dependencies (motor/pymongo).")

    if _is_admin(user):
        jobs = await list_all_jobs(limit=limit, status=status)
    else:
        jobs = await list_user_jobs(user_id=user["id"], limit=limit, status=status)
    out: List[BatchStatusModel] = []
    for j in jobs:
        progress = j.get("progress") or {"current": 0, "total": 0}
        out.append(
            BatchStatusModel(
                job_id=str(j.get("_id")),
                status=j.get("status") or "pending",
                progress=BatchProgress(current=progress.get("current", 0), total=progress.get("total", 0)),
                error=j.get("error"),
                results=None,
                created_at=_iso(j.get("created_at")),
                updated_at=_iso(j.get("updated_at")),
                started_at=_iso(j.get("started_at")),
                finished_at=_iso(j.get("finished_at")),
                duration_ms=(int((j["finished_at"] - j["started_at"]).total_seconds() * 1000)) if j.get("started_at") and j.get("finished_at") else None,
            )
        )
    return out


@router.get("/{job_id}", response_model=BatchStatusModel)
async def get_task(job_id: str, user=Depends(get_current_user)):
    try:
        from app.services.mongo_ops import get_job_for_user, list_job_documents, get_job  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Tasks require Mongo dependencies (motor/pymongo).")

    job = await (get_job(job_id) if _is_admin(user) else get_job_for_user(job_id, user["id"]))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    docs = await list_job_documents(job_id)
    results: List[PDFAnalysisResultModel] = []
    for d in docs:
        if d.get("status") == "done" and d.get("analysis"):
            results.append(
                PDFAnalysisResultModel(
                    **{**(d.get("analysis") or {}), "source_file": d.get("filename") or "unknown.pdf"}
                )
            )
        elif d.get("status") == "error" and d.get("error"):
            results.append(PDFAnalysisResultModel(source_file=d.get("filename") or "unknown.pdf", error=d.get("error")))

    progress = job.get("progress") or {"current": 0, "total": len(docs)}
    status = job.get("status") or "pending"

    return BatchStatusModel(
        job_id=job_id,
        status=status,
        progress=BatchProgress(current=progress.get("current", 0), total=progress.get("total", len(docs))),
        results=results,
        error=job.get("error"),
        created_at=_iso(job.get("created_at")),
        updated_at=_iso(job.get("updated_at")),
        started_at=_iso(job.get("started_at")),
        finished_at=_iso(job.get("finished_at")),
        duration_ms=(int((job["finished_at"] - job["started_at"]).total_seconds() * 1000)) if job.get("started_at") and job.get("finished_at") else None,
    )


@router.post("/{job_id}/cancel")
async def cancel_task(job_id: str, user=Depends(get_current_user)):
    try:
        from app.services.db import get_db  # type: ignore
        from app.services.mongo_ops import get_job_for_user, set_job_status, get_job  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Tasks require Mongo dependencies (motor/pymongo).")

    job = await (get_job(job_id) if _is_admin(user) else get_job_for_user(job_id, user["id"]))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    db = get_db()
    # Mark job as error-cancelled if not already terminal
    if job.get("status") not in {"done", "error"}:
        await set_job_status(job_id, "error", error="cancelled by user")
        await db["documents"].update_many(
            {"job_id": job_id, "status": {"$nin": ["done", "error"]}},
            {"$set": {"status": "error", "error": "cancelled by user"}},
        )
    return {"ok": True}
