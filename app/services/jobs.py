import asyncio
from typing import Dict, Optional
from uuid import uuid4
from app.models.schemas import PDFAnalysisResultModel, BatchStatusModel, BatchProgress  # type: ignore

class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, BatchStatusModel] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(1)  # sequential processing

    @property
    def semaphore(self):
        return self._semaphore

    async def create_job(self, total: int) -> str:
        job_id = uuid4().hex
        async with self._lock:
            self._jobs[job_id] = BatchStatusModel(
                job_id=job_id,
                status="queued",
                progress=BatchProgress(current=0, total=total),
                results=[]
            )
        return job_id

    async def get(self, job_id: str) -> Optional[BatchStatusModel]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_progress(self, job_id: str, current: int):
        async with self._lock:
            job = self._jobs[job_id]
            job.progress.current = current

    async def set_status(self, job_id: str, status: str, error: Optional[str] = None):
        async with self._lock:
            job = self._jobs[job_id]
            job.status = status
            job.error = error

    async def append_result(self, job_id: str, result: PDFAnalysisResultModel):
        async with self._lock:
            job = self._jobs[job_id]
            assert job.results is not None
            job.results.append(result)

job_store = JobStore()
