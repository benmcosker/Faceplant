from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..avatars import save_avatar_bytes
from ..db import get_db
from ..schemas import UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not (1 <= len(normalized) <= 32):
        raise HTTPException(status_code=400, detail="Username must be 1-32 characters.")
    return normalized


@router.get("/{username}", response_model=UserOut)
def get_user(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username.strip().lower()).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.post("", response_model=UserOut)
def claim_user(
    username: str = Form(...),
    avatar: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    normalized = normalize_username(username)
    existing = db.query(models.User).filter(models.User.username == normalized).first()
    if existing is not None:
        return existing

    if avatar is None:
        raise HTTPException(status_code=400, detail="An avatar is required for a new username.")

    data = avatar.file.read()
    avatar_url = save_avatar_bytes(data, avatar.content_type or "")

    user = models.User(username=normalized, avatar_url=avatar_url, is_bot=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
