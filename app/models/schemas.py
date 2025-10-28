from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# --------------------
# Core API Schemas
# --------------------

class PDFAnalysisResultModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    doi: Optional[str] = None
    data_availability_statement: Optional[str] = None
    code_availability_statement: Optional[str] = None
    data_sharing_license: Optional[str] = None
    code_license: Optional[str] = None
    data_links: List[str] = Field(default_factory=list)
    code_links: List[str] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    # For synchronous API responses
    source_file: Optional[str] = None
    # Optional error for per-document failures in batch summaries
    error: Optional[str] = None


class BatchProgress(BaseModel):
    model_config = ConfigDict(extra="ignore")

    current: int
    total: int


class BatchStatusModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: str
    progress: BatchProgress
    results: Optional[List[PDFAnalysisResultModel]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class HealthModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    agent_model: str
    agent_reachable: bool
    embeddings_reachable: bool


# --------------------
# Auth Schemas
# --------------------

class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str = "bearer"


class AuthMeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: str
    is_admin: bool


# --------------------
# Job Logs Schemas
# --------------------

class JobLogEntryModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ts: datetime
    level: str = "info"
    op: Optional[str] = None
    message: Optional[str] = None
    doc_id: Optional[str] = None
    filename: Optional[str] = None
    duration_ms: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None
