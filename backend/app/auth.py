import hashlib
import secrets
from datetime import datetime

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .db import get_db

SESSION_COOKIE_NAME = "faceplant_session"

_serializer = URLSafeTimedSerializer(settings.session_secret_key, salt="faceplant-session")


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
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _read_session_user_id(request: Request) -> int | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
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
