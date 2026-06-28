from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..schemas import LikeResult, LikeToggle

router = APIRouter(prefix="/api/posts", tags=["likes"])


@router.post("/{post_id}/like", response_model=LikeResult)
def toggle_like(post_id: int, payload: LikeToggle, db: Session = Depends(get_db)):
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    normalized = payload.username.strip().lower()
    user = db.query(models.User).filter(models.User.username == normalized).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    existing = (
        db.query(models.Like)
        .filter(models.Like.post_id == post_id, models.Like.user_id == user.id)
        .first()
    )
    if existing is not None:
        db.delete(existing)
        liked = False
    else:
        db.add(models.Like(post_id=post_id, user_id=user.id))
        liked = True
    db.commit()

    count = db.query(func.count(models.Like.id)).filter(models.Like.post_id == post_id).scalar()
    return LikeResult(liked=liked, count=count)
