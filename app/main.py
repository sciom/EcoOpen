import logging
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routes import health, analyze, export, auth, tasks  # type: ignore
from contextlib import asynccontextmanager

# Placeholders to satisfy type checkers; rebound if Mongo deps available
_db_lifespan: Any = None
_start_workers: Any = None
_stop_workers: Any = None

# Try to enable Mongo-backed features if dependencies are present; otherwise run in no-DB mode
try:
    from app.services.db import lifespan as _db_lifespan  # type: ignore
    from app.services.worker_mongo import start_workers as _start_workers, stop_workers as _stop_workers  # type: ignore
    _MONGO_ENABLED = True
except Exception as e:  # ImportError or others
    _MONGO_ENABLED = False
    _MONGO_IMPORT_ERROR = e

@asynccontextmanager
async def lifespan(app: FastAPI):
    if _MONGO_ENABLED:
        assert _db_lifespan is not None and _start_workers is not None and _stop_workers is not None
        async with _db_lifespan(app):
            await _start_workers()
            try:
                yield
            finally:
                await _stop_workers()
    else:
        logging.getLogger(__name__).warning(
            "Mongo dependencies not available; running in no-DB mode (sync analyze only). Error: %s",
            _MONGO_IMPORT_ERROR,
        )
        yield

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO), format='%(asctime)s %(levelname)s %(name)s: %(message)s')

# Startup security warning for default JWT secret
if (settings.JWT_SECRET or "").strip() == "change-me-in-prod":
    logging.getLogger(__name__).warning(
        "JWT_SECRET is using the insecure default. Set a strong secret in production."
    )

app = FastAPI(title="PDF Scientific Data Extractor API", version="0.1.0", lifespan=lifespan)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["meta"])
app.include_router(auth.router, tags=["auth"])
app.include_router(tasks.router, tags=["tasks"])
app.include_router(analyze.router, tags=["analyze"])
app.include_router(export.router, tags=["export"])

@app.get("/")
async def root():
    return {"name": app.title, "version": app.version}


