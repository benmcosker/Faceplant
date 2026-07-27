from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..db import get_db
from ..schemas import LikeResult, UserOut

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


@router.get("/{post_id}/likes", response_model=list[UserOut])
def list_likers(post_id: int, db: Session = Depends(get_db)):
    """The users who liked a post — surfaced on hover over the like count."""
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    return (
        db.query(models.User)
        .join(models.Like, models.Like.user_id == models.User.id)
        .filter(models.Like.post_id == post_id)
        .order_by(models.Like.created_at.desc())
        .all()
    )
