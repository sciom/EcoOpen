from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import traceback
import time
from typing import Optional, List, Any, Dict
from pymongo import ReturnDocument

from app.core.config import settings
from app.services import log_timing
from app.services.agent import AgentRunner
from app.services.db import get_db, read_file_to_path
from app.services.mongo_ops import (
    set_document_status,
    set_document_analysis,
    inc_job_progress,
    get_job,
    set_job_status,
    append_job_log,
    get_running_job,
    promote_next_pending_job,
)


logger = logging.getLogger(__name__)

# Claim only queued documents that belong to the currently running job (or have no job)
_claim_filter = {"status": "queued"}
_claim_update = {"$set": {"status": "processing"}}


async def _claim_next_document() -> Optional[dict]:
    db = get_db()

    # Determine running job and build a claim filter accordingly
    job = await get_running_job()
    claim_filter: Dict[str, Any] = {"status": "queued"}

    if job:
        jid = str(job.get("_id"))
        claim_filter["job_id"] = jid
    else:
        # Try to promote the next pending job
        promoted = await promote_next_pending_job()
        if promoted:
            jid = str(promoted.get("_id"))
            claim_filter["job_id"] = jid
        else:
            # No running/pending jobs; allow jobless documents to proceed
            claim_filter = {"status": "queued", "$or": [{"job_id": None}, {"job_id": {"$exists": False}}]}


    # Return the updated document (after status is set to processing)
    doc = await db["documents"].find_one_and_update(
        claim_filter,
        _claim_update,
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if doc:
        logger.debug("Claimed document %s for processing", str(doc.get("_id")))
    return doc


async def _process_one(doc: dict) -> None:
    grid_id = str(doc.get("gridfs_id"))
    filename = (doc.get("filename") or "document.pdf").replace(os.sep, "_")
    doc_id = str(doc.get("_id"))
    job_id: Optional[str] = doc.get("job_id")

    with tempfile.TemporaryDirectory(prefix="ecoopen_") as td:
        tmp_path = os.path.join(td, filename)
        try:
            # GridFS read with job log instrumentation
            if job_id:
                try:
                    await append_job_log(job_id, op="gridfs_read_start", doc_id=doc_id, filename=filename)
                except Exception:
                    pass
            with log_timing(logger, "gridfs_read", doc_id=doc_id, job_id=job_id, filename=filename):
                t0 = time.perf_counter()
                await read_file_to_path(grid_id, tmp_path)
                if job_id:
                    try:
                        dt_ms = int((time.perf_counter() - t0) * 1000)
                        await append_job_log(
                            job_id,
                            op="gridfs_read_end",
                            doc_id=doc_id,
                            filename=filename,
                            duration_ms=dt_ms,
                        )
                    except Exception:
                        pass

            # Analyze with job log instrumentation
            agent = AgentRunner(context={"doc_id": doc_id, "job_id": job_id, "filename": filename})
            if job_id:
                try:
                    await append_job_log(job_id, op="analyze_pdf_start", doc_id=doc_id, filename=filename)
                except Exception:
                    pass
            with log_timing(logger, "analyze_pdf", doc_id=doc_id, job_id=job_id, filename=filename):
                t1 = time.perf_counter()
                model_res = await asyncio.to_thread(agent.analyze, tmp_path)
                if job_id:
                    try:
                        dt_ms = int((time.perf_counter() - t1) * 1000)
                        await append_job_log(
                            job_id,
                            op="analyze_pdf_end",
                            doc_id=doc_id,
                            filename=filename,
                            duration_ms=dt_ms,
                        )
                    except Exception:
                        pass

            await set_document_analysis(doc_id, model_res.model_dump())
        except Exception as e:
            # Capture stack for easier debugging and surface a descriptive error message
            tb = traceback.format_exc()
            err_text = f"{e.__class__.__name__}: {e}"
            logger.exception("Worker failed processing doc_id=%s file=%s", doc_id, filename)
            # Truncate to avoid oversized Mongo docs; include tail of traceback where the error is
            tail = tb[-2000:]
            if job_id:
                try:
                    await append_job_log(
                        job_id,
                        level="error",
                        op="error",
                        message=err_text,
                        doc_id=doc_id,
                        filename=filename,
                        extra={"traceback_tail": tail},
                    )
                except Exception:
                    pass
            await set_document_status(doc_id, "error", error=f"{err_text}\n{tail}")
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                # File already removed or doesn't exist
                pass

    # Update job progress regardless of success or error
    if job_id:
        await inc_job_progress(job_id, by=1)
        job = await get_job(job_id)
        if job:
            cur = ((job.get("progress") or {}).get("current")) or 0
            total = ((job.get("progress") or {}).get("total")) or 0
            if cur >= total and (job.get("status") != "done"):
                await set_job_status(job_id, "done")
                # After finishing a job, try to promote the next one
                try:
                    await promote_next_pending_job()
                except Exception:
                    pass


class MongoWorker:
    def __init__(self, concurrency: int = 1, poll_interval: float = 0.5) -> None:
        self.concurrency = max(1, concurrency)
        self.poll_interval = poll_interval
        self._stop = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        for _ in range(self.concurrency):
            t = asyncio.create_task(self._run())
            self._tasks.append(t)

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                doc = await _claim_next_document()
                if not doc:
                    await asyncio.sleep(self.poll_interval)
                    continue
                try:
                    await _process_one(doc)
                except Exception as e:
                    # Best effort: mark as error if not already; also log details
                    logger.exception("Unhandled worker error while processing doc_id=%s", str(doc.get("_id")))
                    try:
                        did = str(doc.get("_id"))
                        tb = traceback.format_exc()
                        err_text = f"{e.__class__.__name__}: {e}"
                        tail = tb[-2000:]
                        job_id = doc.get("job_id")
                        filename = (doc.get("filename") or "document.pdf").replace(os.sep, "_")
                        if job_id:
                            try:
                                await append_job_log(
                                    job_id,
                                    level="error",
                                    op="error",
                                    message=err_text,
                                    doc_id=did,
                                    filename=filename,
                                    extra={"traceback_tail": tail},
                                )
                            except Exception:
                                pass
                        await set_document_status(did, "error", error=f"{err_text}\n{tail}")
                    except Exception:
                        pass
        except asyncio.CancelledError:
            return


_worker: Optional[MongoWorker] = None


async def start_workers() -> None:
    global _worker
    _worker = MongoWorker(concurrency=settings.QUEUE_CONCURRENCY)
    await _worker.start()


async def stop_workers() -> None:
    global _worker
    if _worker is not None:
        await _worker.stop()
        _worker = None
