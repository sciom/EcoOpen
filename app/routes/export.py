import csv
import io
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# Lazy import in handler to allow running without Mongo deps when unused

router = APIRouter()

_security = HTTPBearer(auto_error=False)

async def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_security)) -> dict:
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


def _is_admin(user: dict) -> bool:
    try:
        email = (user.get("email") or "").strip().lower()
    except Exception:
        return False
    return email in (settings.ADMIN_EMAILS or [])


@router.get("/export/csv/{job_id}")
async def export_csv(job_id: str, user: dict = Depends(_get_current_user)):
    try:
        from app.services.mongo_ops import get_job_for_user as mongo_get_job_for_user, list_job_documents, get_job  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Export requires Mongo dependencies (motor/pymongo).")

    job = await (get_job(job_id) if _is_admin(user) else mongo_get_job_for_user(job_id, user["id"]))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    docs = await list_job_documents(job_id)
    finished = [d for d in docs if d.get("status") in {"done", "error"}]
    if not finished:
        raise HTTPException(status_code=400, detail="Job has no results yet")

    buf = io.StringIO()
    fieldnames = [
        "source_file",
        "filename",
        "title",
        "doi",
        "doi_from_title_search",
        "data_availability_statement",
        "code_availability_statement",
        "data_sharing_license",
        "code_license",
        "data_links_count",
        "code_links_count",
        "data_links",
        "code_links",
        "error",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()

    for d in finished:
        analysis = d.get("analysis") or {}
        filename = d.get("filename") or "unknown.pdf"
        data_links = analysis.get("data_links") or []
        code_links = analysis.get("code_links") or []
        writer.writerow(
            {
                "source_file": filename,
                "filename": filename.split("/")[-1],
                "title": analysis.get("title") or "",
                "doi": analysis.get("doi") or "",
                "doi_from_title_search": "",  # optional enrichment could be added server-side
                "data_availability_statement": analysis.get("data_availability_statement") or "",
                "code_availability_statement": analysis.get("code_availability_statement") or "",
                "data_sharing_license": analysis.get("data_sharing_license") or "",
                "code_license": analysis.get("code_license") or "",
                "data_links_count": len(data_links),
                "code_links_count": len(code_links),
                "data_links": "; ".join(data_links),
                "code_links": "; ".join(code_links),
                "error": d.get("error") or analysis.get("error") or "",
            }
        )

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="analysis_{job_id}.csv"'},
    )
