from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class PDFAnalysisResultModel(BaseModel):
    title: Optional[str] = None
    doi: Optional[str] = None
    data_availability_statement: Optional[str] = None
    code_availability_statement: Optional[str] = None
    data_sharing_license: Optional[str] = None
    code_license: Optional[str] = None
    data_links: List[str] = Field(default_factory=list)
    code_links: List[str] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)

    source_file: Optional[str] = None
    error: Optional[str] = None

class BatchProgress(BaseModel):
    current: int
    total: int

class BatchStatusModel(BaseModel):
    job_id: str
    status: str  # queued|running|done|error
    progress: BatchProgress
    results: Optional[List[PDFAnalysisResultModel]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None

class HealthModel(BaseModel):
    status: str
    agent_model: str
    agent_reachable: bool
    embeddings_reachable: bool

# --- Auth / Users ---
class UserPublic(BaseModel):
    id: str
    email: str
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
