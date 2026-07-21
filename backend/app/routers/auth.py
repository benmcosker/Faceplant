from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    clear_session_cookie,
    generate_token,
    get_current_user,
    hash_token,
    set_session_cookie,
    utcnow,
)
from ..avatars import save_avatar_bytes
from ..config import settings
from ..db import get_db
from ..email import send_magic_link_email
from ..schemas import RequestLinkIn, UserOut, VerifyIn, VerifyOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not (1 <= len(normalized) <= 32):
        raise HTTPException(status_code=400, detail="Username must be 1-32 characters.")
    return normalized


@router.post("/request-link", status_code=202)
def request_link(payload: RequestLinkIn, db: Session = Depends(get_db)):
    """Always 202s regardless of whether the email is known, so this endpoint
    never reveals which addresses have accounts."""
    email = payload.email.strip().lower()
    token = generate_token()
    record = models.MagicLinkToken(
        email=email,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(minutes=settings.magic_link_token_ttl_minutes),
    )
    db.add(record)
    db.commit()

    link = f"{settings.frontend_url}/?token={token}"
    send_magic_link_email(email, link)
    return {"ok": True}


def _find_valid_token(db: Session, token: str) -> models.MagicLinkToken:
    record = (
        db.query(models.MagicLinkToken)
        .filter(models.MagicLinkToken.token_hash == hash_token(token))
        .first()
    )
    if record is None or record.used_at is not None or record.expires_at < utcnow():
        raise HTTPException(status_code=400, detail="This link is invalid or has expired.")
    return record


@router.post("/verify", response_model=VerifyOut)
def verify(payload: VerifyIn, response: Response, db: Session = Depends(get_db)):
    record = _find_valid_token(db, payload.token)

    user = db.query(models.User).filter(models.User.email == record.email).first()
    if user is None:
        # Don't consume the token yet — /signup still needs it to prove
        # ownership of this email for the account it's about to create.
        return VerifyOut(status="new", email=record.email)

    record.used_at = utcnow()
    db.commit()
    set_session_cookie(response, user.id)
    return VerifyOut(status="logged_in", user=user)


@router.post("/signup", response_model=UserOut)
def signup(
    response: Response,
    token: str = Form(...),
    username: str = Form(...),
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    record = _find_valid_token(db, token)

    normalized = normalize_username(username)
    if db.query(models.User).filter(models.User.username == normalized).first() is not None:
        raise HTTPException(status_code=409, detail="Username is already taken.")
    if db.query(models.User).filter(models.User.email == record.email).first() is not None:
        raise HTTPException(status_code=409, detail="An account already exists for this email.")

    data = avatar.file.read()
    avatar_url = save_avatar_bytes(data, avatar.content_type or "")

    user = models.User(username=normalized, email=record.email, avatar_url=avatar_url, is_bot=False)
    db.add(user)
    record.used_at = utcnow()
    db.commit()
    db.refresh(user)

    set_session_cookie(response, user.id)
    return user


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}
