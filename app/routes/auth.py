from __future__ import annotations

import datetime as dt
from typing import Optional, Dict, Any, Tuple, Any
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from app.core.config import settings
from app.models.schemas import UserPublic, TokenResponse, AuthMeResponse

router = APIRouter(prefix="/auth")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


def _try_import_jose() -> Tuple[Optional[object], Optional[Exception]]:
    try:
        from jose import jwt, JWTError  # type: ignore
        return (jwt, JWTError)  # type: ignore
    except Exception as e:
        return (None, e)


def _require_jose():
    jwt_tuple = _try_import_jose()
    if not jwt_tuple[0]:
        raise HTTPException(status_code=503, detail="Auth requires python-jose (install dependencies).")
    return jwt_tuple


def _create_access_token(sub: str, email: str) -> str:
    jwt, _ = _require_jose()
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=settings.JWT_EXPIRES_MINUTES)
    payload = {"sub": sub, "email": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)  # type: ignore


class UserCreateModel:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password


class LoginModel:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password


@router.post("/register", response_model=UserPublic)
async def register(body: Dict[str, Any]):
    try:
        # Lazy import to avoid ImportError when Mongo deps are missing
        from app.services.db import get_db  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Auth requires Mongo dependencies (motor/pymongo).")

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    password_confirm = body.get("password_confirm") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    if password != password_confirm:
        raise HTTPException(status_code=400, detail="password and password_confirm do not match")

    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters and include letters and numbers")

    db = get_db()
    existing = await db["users"].find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = {
        "email": email,
        "password_hash": _hash_password(password),
        "created_at": dt.datetime.utcnow().isoformat(),
    }
    res = await db["users"].insert_one(doc)

    return UserPublic(id=str(res.inserted_id), email=email, created_at=doc["created_at"])  # type: ignore


@router.post("/login", response_model=TokenResponse)
async def login(body: Dict[str, Any]):
    try:
        from app.services.db import get_db  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Auth requires Mongo dependencies (motor/pymongo).")

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    db = get_db()
    user = await db["users"].find_one({"email": email})
    if not user or not _verify_password(password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_access_token(str(user["_id"]), email)
    return TokenResponse(access_token=token)  # type: ignore


# /auth/me defined after get_current_user


async def get_bearer_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    return credentials.credentials


async def get_optional_user(token: Optional[str] = Depends(get_bearer_token)) -> Optional[Dict[str, str]]:
    if not token:
        return None
    jwt_tuple = _try_import_jose()
    if not jwt_tuple[0]:
        # If auth libs are missing, treat as unauthenticated for optional path
        return None
    jwt, JWTError = jwt_tuple  # type: ignore
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])  # type: ignore
        sub = str(payload.get("sub") or "").strip()
        email = str(payload.get("email") or "").strip()
        if not sub:
            return None
        return {"id": sub, "email": email}
    except JWTError:  # type: ignore
        return None


async def get_current_user(token: Optional[str] = Depends(get_bearer_token)) -> Dict[str, str]:
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    jwt, JWTError = _require_jose()  # type: ignore
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])  # type: ignore
        sub = str(payload.get("sub") or "").strip()
        email = str(payload.get("email") or "").strip()
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:  # type: ignore
        raise HTTPException(status_code=401, detail="Invalid token")

    # Optionally confirm user still exists; if Mongo missing, surface 503 for strict dependency
    try:
        from app.services.db import get_db  # type: ignore
        from bson import ObjectId  # type: ignore
        db = get_db()
        user = await db["users"].find_one({"_id": ObjectId(sub)})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except HTTPException:
        raise
    except Exception:
        # If Mongo deps missing or lookup fails, report service unavailable for strict auth
        raise HTTPException(status_code=503, detail="Auth requires Mongo dependencies (motor/pymongo).")

    return {"id": sub, "email": email}


@router.get("/me", response_model=AuthMeResponse)
async def auth_me(user: Dict[str, str] = Depends(get_current_user)):
    email = (user.get("email") or "").strip().lower()
    is_admin = email in (settings.ADMIN_EMAILS or [])
    return AuthMeResponse(id=user["id"], email=email, is_admin=is_admin)  # type: ignore
