from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
import logging
from typing import Any, AsyncIterator, Dict, Optional, TYPE_CHECKING

# Avoid hard dependency on Mongo/BSON at import time so tests can monkeypatch
if TYPE_CHECKING:  # type-only imports
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
else:  # runtime fallbacks to keep module importable
    AsyncIOMotorClient = Any  # type: ignore
    AsyncIOMotorDatabase = Any  # type: ignore
    AsyncIOMotorGridFSBucket = Any  # type: ignore

from fastapi import FastAPI

from app.core.config import settings

logger = logging.getLogger(__name__)


class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    fs: Optional[AsyncIOMotorGridFSBucket] = None


def get_db() -> AsyncIOMotorDatabase:
    if Database.db is None:
        raise RuntimeError("Database not initialized. Ensure FastAPI lifespan started and MongoDB is reachable.")
    return Database.db


def get_fs() -> AsyncIOMotorGridFSBucket:
    if Database.fs is None:
        raise RuntimeError("GridFS not initialized. Ensure FastAPI lifespan started and MongoDB is reachable.")
    return Database.fs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        # Import motor lazily to avoid ImportError when dependencies are missing
        from motor.motor_asyncio import AsyncIOMotorClient as _Client, AsyncIOMotorGridFSBucket as _Grid
    except Exception as e:
        logger.error("Mongo dependencies not available: %s", e)
        raise RuntimeError(f"MongoDB dependencies not available: {e}")

    try:
        Database.client = _Client(settings.MONGO_URI)
        # Force a quick server selection to fail fast if Mongo is down
        await Database.client.server_info()
    except Exception as e:
        logger.error("Failed to connect to MongoDB at %s: %s", settings.MONGO_URI, e)
        raise RuntimeError(f"MongoDB connection failed: {e}")

    Database.db = Database.client[settings.MONGO_DB_NAME]
    Database.fs = _Grid(Database.db)

    # Indexes
    await Database.db["documents"].create_index("sha256", unique=False)
    await Database.db["documents"].create_index("status")
    await Database.db["documents"].create_index("created_at")
    await Database.db["documents"].create_index("user_id")
    await Database.db["jobs"].create_index("created_at")
    await Database.db["jobs"].create_index("status")
    await Database.db["jobs"].create_index("user_id")
    await Database.db["users"].create_index("email", unique=True)
    # Job logs indexes
    await Database.db["job_logs"].create_index([("job_id", 1), ("ts", 1)])
    await Database.db["job_logs"].create_index("ts")

    try:
        yield
    finally:
        if Database.client:
            Database.client.close()


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def put_file(content: bytes, filename: str, content_type: str, metadata: Dict[str, Any]) -> str:
    fs = get_fs()
    stream = fs.open_upload_stream(filename, metadata={**metadata, "content_type": content_type})
    try:
        await stream.write(content)
    finally:
        await stream.close()
    return str(stream._id)


async def read_file_to_path(file_id: str, path: str) -> None:
    fs = get_fs()
    try:
        from bson import ObjectId as _ObjectId  # lazy import to avoid import-time failure
    except Exception as e:
        raise RuntimeError(f"BSON dependency not available: {e}")
    oid = _ObjectId(file_id) if not isinstance(file_id, _ObjectId) else file_id
    stream = None
    try:
        # In Motor v3+, open_download_stream is async
        stream = await fs.open_download_stream(oid)
        with open(path, "wb") as out:
            while True:
                # Read in 1MB chunks (works across Motor versions)
                chunk = await stream.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    finally:
        if stream is not None:
            try:
                await stream.close()
            except TypeError:
                # Some versions expose a sync close()
                try:
                    stream.close()
                except Exception:
                    pass
            except Exception:
                pass


