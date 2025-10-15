from fastapi import APIRouter
import httpx
from app.core.config import settings
from app.models.schemas import HealthModel

router = APIRouter()

@router.get("/health", response_model=HealthModel)
async def health() -> HealthModel:
    agent_ok = False
    embed_ok = False

    # Check agent/LLM endpoint (OpenAI-compatible /models or Ollama /api/tags)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {}
            if settings.AGENT_API_KEY:
                headers["Authorization"] = f"Bearer {settings.AGENT_API_KEY}"
            base = settings.AGENT_BASE_URL.rstrip("/")
            bases = {base, base.removesuffix("/v1")} if base.endswith("/v1") else {base}
            paths = []
            for b in bases:
                paths.extend([f"{b}/models", f"{b}/v1/models", f"{b}/api/tags"])  # Ollama
            agent_ok = False
            for url in paths:
                try:
                    r = await client.get(url, headers=headers)
                except Exception:
                    continue
                if r.status_code == 200:
                    try:
                        data = r.json()
                        # OpenAI style
                        models = data.get("data") or data.get("models")
                        if isinstance(models, list) and len(models) >= 1:
                            agent_ok = True
                            break
                        # Ollama style
                        if isinstance(data, dict) and isinstance(data.get("models"), list) and len(data["models"]) >= 1:
                            agent_ok = True
                            break
                    except Exception:
                        continue
    except Exception:
        agent_ok = False

    # Check embeddings (Ollama host + required embed model available)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.OLLAMA_HOST.rstrip('/')}/api/tags")
            if r.status_code < 500:
                embed_ok = True
                try:
                    data = r.json()
                    models = data.get("models") or []
                    names = {m.get("name") or m.get("model") for m in models}
                    # Accept names that match exactly or with a tag suffix like ":latest"
                    required = settings.OLLAMA_EMBED_MODEL
                    found = False
                    for n in names:
                        if not n:
                            continue
                        if n == required or n.startswith(f"{required}:"):
                            found = True
                            break
                    if not found:
                        embed_ok = False
                except Exception:
                    # If we can't parse, leave embed_ok as host reachability indicator
                    pass
            else:
                embed_ok = False
    except Exception:
        embed_ok = False

    return HealthModel(
        status="ok" if agent_ok and embed_ok else "degraded",
        agent_model=settings.AGENT_MODEL,
        agent_reachable=agent_ok,
        embeddings_reachable=embed_ok,
    )

@router.get("/config")
async def get_config():
    return {
        "agent_base_url": settings.AGENT_BASE_URL,
        "agent_model": settings.AGENT_MODEL,
        "ollama_host": settings.OLLAMA_HOST,
        "ollama_model": settings.OLLAMA_MODEL,
        "ollama_embed_model": settings.OLLAMA_EMBED_MODEL,
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "cors_origins": settings.CORS_ORIGINS,
    }
