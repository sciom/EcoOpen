import os
import json
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # pydantic-settings v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Agent / LLM (OpenAI-compatible or Ollama endpoints)
    # Default to local OpenAI-compatible endpoint (e.g., Ollama's /v1 or a proxy)
    AGENT_BASE_URL: str = Field(default="http://localhost:11434/v1")
    # Sensible local default; override via ENV to your hosted model id
    AGENT_MODEL: str = Field(default="llama3.1")
    AGENT_API_KEY: Optional[str] = Field(default=None)
    # HTTP timeout for agent calls in seconds (big models may need more time)
    AGENT_TIMEOUT_SECONDS: int = Field(default=120, ge=5, le=1800)

    # Embeddings / Ollama (local)
    OLLAMA_HOST: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="phi3:mini")
    OLLAMA_EMBED_MODEL: str = Field(default="nomic-embed-text")

    # Embeddings backend selection: 'ollama' or 'endpoint'
    EMBEDDINGS_BACKEND: str = Field(default="ollama")
    # Embedding model when using AGENT endpoint
    AGENT_EMBED_MODEL: str = Field(default="text-embedding-3-small")

    # App
    MAX_FILE_SIZE_MB: int = Field(default=50, ge=1, le=500)
    # Accept JSON array or comma-separated string in ENV
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

    # Chroma
    CHROMA_DB_PATH: str = Field(default="./chroma_db")

    # MongoDB
    MONGO_URI: str = Field(default="mongodb://localhost:27017")
    MONGO_DB_NAME: str = Field(default="ecoopen")

    # Worker concurrency (Mongo-based background worker)
    QUEUE_CONCURRENCY: int = Field(default=1, ge=1)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")  # DEBUG|INFO|WARNING|ERROR|CRITICAL

    # Auth
    JWT_SECRET: str = Field(default="change-me-in-prod")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRES_MINUTES: int = Field(default=60, ge=5, le=7 * 24 * 60)

    # MCP (Model Context Protocol)
    MCP_ENABLED: bool = Field(default=False)
    MCP_SERVER_URL: str = Field(default="ws://localhost:5174")
    MCP_TOOL_NAME: str = Field(default="chat_complete")

    # Repair toggles
    REPAIR_CONTEXT_ENABLED: bool = Field(default=True)
    REPAIR_URLS_ENABLED: bool = Field(default=True)

    # --- Validators / Normalizers ---
    @field_validator("AGENT_BASE_URL", mode="before")
    @classmethod
    def _normalize_base_url(cls, v: Union[str, None]) -> str:
        if not v:
            return "http://localhost:11434/v1"
        s = str(v).strip().rstrip("/")
        return s

    @field_validator("AGENT_API_KEY", mode="before")
    @classmethod
    def _normalize_agent_key(cls, v: Union[str, None]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("AGENT_MODEL", mode="before")
    @classmethod
    def _normalize_agent_model(cls, v: Union[str, None]) -> str:
        s = str(v).strip() if v is not None else ""
        return s or "llama3.1"

    @field_validator("OLLAMA_HOST", mode="before")
    @classmethod
    def _normalize_ollama_host(cls, v: Union[str, None]) -> str:
        if not v:
            return "http://localhost:11434"
        return str(v).strip().rstrip("/")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        # Accept list, JSON string, or comma-separated string
        if v is None:
            return ["http://localhost:5173"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            # Try JSON array first
            if s.startswith("["):
                try:
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return arr
                except Exception:
                    pass
            # Fallback: comma-separated
            return [p.strip() for p in s.split(",") if p.strip()]
        # Unknown type -> cast to list of strings if possible
        try:
            return list(v)
        except Exception:
            return ["http://localhost:5173"]

    @field_validator("CHROMA_DB_PATH", mode="before")
    @classmethod
    def _normalize_chroma_path(cls, v: Union[str, None]) -> str:
        p = (v or "./chroma_db").strip()
        # Expand ~ and make absolute to avoid surprises with working dir
        return os.path.abspath(os.path.expanduser(p))

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalize_log_level(cls, v: Union[str, None]) -> str:
        lv = str(v).strip().upper() if v is not None else "INFO"
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        return lv if lv in allowed else "INFO"

    @field_validator("MCP_SERVER_URL", mode="before")
    @classmethod
    def _normalize_mcp_url(cls, v: Union[str, None]) -> str:
        if not v:
            return "ws://localhost:5174"
        return str(v).strip()

settings = Settings()
