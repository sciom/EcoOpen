import os
import hashlib
import asyncio
from typing import List, Literal, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.validation import sanitize_filename, validate_file_extension
from app.models.schemas import PDFAnalysisResultModel, BatchStatusModel, BatchProgress
from app.services.agent import AgentRunner
from app.core.errors import (
    InvalidPDFError,
    PDFReadError,
    EmbeddingModelMissingError,
    LLMServiceError,
)
# Queue removed (Mongo-only worker); direct status update triggers worker pickup

router = APIRouter()

def _is_admin(user: dict) -> bool:
    try:
        email = (user.get("email") or "").strip().lower()
    except Exception:
        return False
    return email in (settings.ADMIN_EMAILS or [])

MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024

_security = HTTPBearer(auto_error=False)

async def _get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security)) -> Optional[dict]:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    token = credentials.credentials
    try:
        # Lazy import to avoid hard dependency during module import
        from jose import jwt, JWTError  # type: ignore
    except Exception:
        # If auth libs are missing, treat as unauthenticated for optional path
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        sub = str(payload.get("sub") or "").strip()
        email = str(payload.get("email") or "").strip()
        if not sub:
            return None
        return {"id": sub, "email": email}
    except Exception:
        return None


async def _get_required_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security)) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        from jose import jwt, JWTError  # type: ignore
    except Exception:
        # Auth strictly requires python-jose
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



def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_pdf(file: UploadFile):
    """Validate that the uploaded file is a PDF."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)

    # Check extension
    if not validate_file_extension(safe_filename, {".pdf"}):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    return safe_filename


def _to_result_model(analysis: dict, source_file: str) -> PDFAnalysisResultModel:
    return PDFAnalysisResultModel(
        title=analysis.get("title"),
        doi=analysis.get("doi"),
        data_availability_statement=analysis.get("data_availability_statement"),
        code_availability_statement=analysis.get("code_availability_statement"),
        data_sharing_license=analysis.get("data_sharing_license"),
        code_license=analysis.get("code_license"),
        data_links=analysis.get("data_links") or [],
        code_links=analysis.get("code_links") or [],
        confidence_scores=analysis.get("confidence_scores") or {},
        source_file=source_file,
    )


@router.post("/analyze", response_model=PDFAnalysisResultModel)
async def analyze(file: UploadFile = File(...),
                  mode: Literal["auto", "sync", "queue"] = Query(default="auto"),
                  user: dict = Depends(_get_required_user)):
    """
    Analyze a single PDF file for data and code availability information. Requires authentication.
    """
    safe_filename = _validate_pdf(file)
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit")

    # Synchronous path focuses on core PDF reading and analysis without DB dependency
    if mode == "sync":
        tmp_path = f"/tmp/{os.getpid()}_{safe_filename}"
        with open(tmp_path, "wb") as f:
            f.write(content)
        try:
            agent = AgentRunner()
            model_res = await asyncio.to_thread(agent.analyze, tmp_path)
            model_res.source_file = safe_filename
            return model_res
        except EmbeddingModelMissingError as e:
            raise HTTPException(status_code=400, detail={"message": str(e), "model": settings.OLLAMA_EMBED_MODEL, "code": "embed_model_missing"})
        except InvalidPDFError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except LLMServiceError as e:
            # Vital dependency; surface as 502 Bad Gateway
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    # Default: queue mode uses Mongo + worker, with polling and sync fallback
    # Lazily import Mongo-dependent modules to allow sync mode without Mongo/motor installed
    try:
        from app.services.db import put_file  # type: ignore
        from app.services.mongo_ops import (
            create_document,
            set_document_status,
            set_document_analysis,
            get_document,
            create_job,
            set_document_job_id,
        )  # type: ignore
    except ImportError:
        # If queue was explicitly requested, surface 503. Otherwise, fall back to sync.
        if mode == "queue":
            raise HTTPException(status_code=503, detail="Queue mode requires Mongo dependencies (motor/pymongo). Install them or use mode=sync.")
        # Fallback to synchronous processing to keep UX working without Mongo
        tmp_path = f"/tmp/{os.getpid()}_{safe_filename}"
        with open(tmp_path, "wb") as f:
            f.write(content)
        try:
            agent = AgentRunner()
            model_res = await asyncio.to_thread(agent.analyze, tmp_path)
            model_res.source_file = safe_filename
            return model_res
        except EmbeddingModelMissingError as e:
            raise HTTPException(status_code=400, detail={"message": str(e), "model": settings.OLLAMA_EMBED_MODEL, "code": "embed_model_missing"})
        except InvalidPDFError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except LLMServiceError as e:
            # Vital dependency; surface as 502 Bad Gateway
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    checksum = _compute_sha256(content)
    grid_id = await put_file(content, safe_filename, file.content_type or "application/pdf", {
        "filename": safe_filename,
        "size": len(content),
        "sha256": checksum,
    })
    doc_id = await create_document(
        filename=safe_filename,
        content_type=file.content_type or "application/pdf",
        size=len(content),
        sha256=checksum,
        gridfs_id=grid_id,
        job_id=None,
        user_id=(user["id"] if user else None),
    )

    # Create a job per single analyze to enable job logs
    job_id = await create_job(total=1, document_ids=[doc_id], user_id=(user["id"] if user else None))
    await set_document_job_id(doc_id, job_id)
    await set_document_status(doc_id, "queued")

    # Poll for a short period for worker result; fall back to sync
    timeout_s = 20.0
    interval_s = 0.5
    waited = 0.0
    while waited < timeout_s:
        d = await get_document(doc_id)
        if d and d.get("status") in {"done", "error"}:
            if d.get("status") == "done" and d.get("analysis"):
                return _to_result_model(d["analysis"], d.get("filename") or safe_filename)
            err = d.get("error") or "Analysis failed"
            raise HTTPException(status_code=500, detail=err)
        await asyncio.sleep(interval_s)
        waited += interval_s

    # Fallback: run sync, persist into document for consistency
    tmp_path = f"/tmp/{os.getpid()}_{safe_filename}"
    with open(tmp_path, "wb") as f:
        f.write(content)
    try:
        agent = AgentRunner()
        model_res = agent.analyze(tmp_path)
        model_res.source_file = safe_filename
        try:
            await set_document_analysis(doc_id, {
                "title": model_res.title,
                "doi": model_res.doi,
                "data_availability_statement": model_res.data_availability_statement,
                "code_availability_statement": model_res.code_availability_statement,
                "data_sharing_license": model_res.data_sharing_license,
                "code_license": model_res.code_license,
                "data_links": model_res.data_links,
                "code_links": model_res.code_links,
                "confidence_scores": model_res.confidence_scores,
            })
        except Exception:
            # Don't fail the request if persisting fails
            pass
        return model_res
    except EmbeddingModelMissingError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "model": settings.OLLAMA_EMBED_MODEL, "code": "embed_model_missing"})
    except InvalidPDFError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@router.post("/analyze/batch", response_model=BatchStatusModel)
async def analyze_batch(files: List[UploadFile] = File(...), user: dict = Depends(_get_required_user)):
    """Queue multiple PDFs for analysis; returns a job to poll. Requires authentication."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    try:
        from app.services.db import put_file  # type: ignore
        from app.services.mongo_ops import (
            create_document,
            create_job,
            set_document_job_id,
            set_document_status,
        )  # type: ignore
    except ImportError:
        raise HTTPException(status_code=503, detail="Batch analyze requires Mongo dependencies (motor/pymongo).")

    doc_ids: List[str] = []
    for f in files:
        safe_filename = _validate_pdf(f)
        content = await f.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(status_code=400, detail=f"File {safe_filename} exceeds {settings.MAX_FILE_SIZE_MB} MB limit")
        checksum = _compute_sha256(content)
        grid_id = await put_file(content, safe_filename, f.content_type or "application/pdf", {
            "filename": safe_filename,
            "size": len(content),
            "sha256": checksum,
        })
        doc_id = await create_document(
            filename=safe_filename,
            content_type=f.content_type or "application/pdf",
            size=len(content),
            sha256=checksum,
            gridfs_id=grid_id,
            job_id=None,
            user_id=user["id"],
        )
        doc_ids.append(doc_id)

    job_id = await create_job(total=len(doc_ids), document_ids=doc_ids, user_id=user["id"])

    for did in doc_ids:
        await set_document_job_id(did, job_id)
        await set_document_status(did, "queued")

    # Leave job in pending; dispatcher/worker will promote when ready
    return BatchStatusModel(job_id=job_id, status="pending", progress=BatchProgress(current=0, total=len(doc_ids)), results=[])


@router.get("/jobs/{job_id}", response_model=BatchStatusModel)
async def get_job(job_id: str, user: dict = Depends(_get_required_user)):
    try:
        from app.services.mongo_ops import (
            get_job_for_user,
            list_job_documents,
            get_job,
        )  # type: ignore
    except ImportError:
        raise HTTPException(status_code=503, detail="Job status requires Mongo dependencies (motor/pymongo).")

    job = await (get_job(job_id) if _is_admin(user) else get_job_for_user(job_id, user["id"]))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Build results from finished documents
    docs = await list_job_documents(job_id)
    results: List[PDFAnalysisResultModel] = []
    for d in docs:
        if d.get("status") == "done" and d.get("analysis"):
            results.append(_to_result_model(d["analysis"], d.get("filename") or "unknown.pdf"))
        elif d.get("status") == "error" and d.get("error"):
            results.append(PDFAnalysisResultModel(source_file=d.get("filename") or "unknown.pdf", error=d.get("error")))

    progress = job.get("progress") or {"current": 0, "total": len(docs)}
    status = job.get("status") or "pending"

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
