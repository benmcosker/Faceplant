from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..db import get_db
from ..schemas import LikeResult

router = APIRouter(prefix="/api/posts", tags=["likes"])


@router.post("/{post_id}/like", response_model=LikeResult)
def toggle_like(
    post_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

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
