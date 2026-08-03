import hashlib
import secrets
from datetime import datetime

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .db import get_db

SESSION_COOKIE_BASE_NAME = "faceplant_session"

_serializer = URLSafeTimedSerializer(settings.session_secret_key, salt="faceplant-session")


def _cookie_name() -> str:
    """The session cookie's name, optionally hardened with the __Host- prefix.

    The prefix binds the cookie to this exact origin; the browser enforces that
    it carry Secure + Path=/ and no Domain (config validates the Secure part).
    """
    prefix = "__Host-" if settings.cookie_host_prefix else ""
    return f"{prefix}{SESSION_COOKIE_BASE_NAME}"


def utcnow() -> datetime:
    # Naive UTC, matching the rest of the app (e.g. costs.py, reactions.py) —
    # keeps this comparable to DateTime columns, which round-trip as naive on
    # both SQLite (tests) and the DateTime type used elsewhere here.
    return datetime.utcnow()


def generate_token() -> str:
    """A single-use magic-link token. Only its hash is ever stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_session_cookie(response: Response, user_id: int) -> None:
    token = _serializer.dumps(user_id)
    response.set_cookie(
        key=_cookie_name(),
        value=token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    # Mirror the attributes used when setting so the delete matches the cookie
    # the browser is holding (Secure / SameSite must line up, especially for a
    # SameSite=None or __Host- cookie).
    response.delete_cookie(
        key=_cookie_name(),
        path="/",
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


def _read_session_user_id(request: Request) -> int | None:
    token = request.cookies.get(_cookie_name())
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=settings.session_ttl_days * 86400)
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user_id = _read_session_user_id(request)
    if user_id is not None:
        user = db.get(models.User, user_id)
        if user is not None:
            return user
    raise HTTPException(status_code=401, detail="Not logged in.")
