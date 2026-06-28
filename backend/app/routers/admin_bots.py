from fastapi import APIRouter, Depends, Header, HTTPException
from passlib.hash import bcrypt
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import get_db
from ..schemas import AdminBotCreate, UserOut

router = APIRouter(prefix="/api/admin/bots", tags=["admin"])


def require_admin(x_admin_key: str = Header(...)) -> None:
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key.")


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_admin)])
def list_bots(db: Session = Depends(get_db)):
    return db.query(models.User).filter(models.User.is_bot.is_(True)).all()


def create_bot_account(db: Session, payload: AdminBotCreate) -> models.User:
    normalized = payload.username.strip().lower()
    existing = db.query(models.User).filter(models.User.username == normalized).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username is already taken.")

    bot = models.User(
        username=normalized,
        avatar_url=payload.avatar_url,
        is_bot=True,
        password_hash=bcrypt.hash(payload.password),
        persona=payload.persona,
        bot_model=payload.model or settings.default_bot_model,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


@router.post("", response_model=UserOut, dependencies=[Depends(require_admin)])
def create_bot(payload: AdminBotCreate, db: Session = Depends(get_db)):
    return create_bot_account(db, payload)
