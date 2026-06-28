from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..bots.reactions import enqueue_reactions_for_post
from ..db import get_db
from ..schemas import PostCreate, PostOut

router = APIRouter(prefix="/api/posts", tags=["posts"])


def _to_post_out(db: Session, post: models.Post) -> PostOut:
    author = db.get(models.User, post.user_id)
    like_count = db.query(func.count(models.Like.id)).filter(models.Like.post_id == post.id).scalar()
    comment_count = (
        db.query(func.count(models.Comment.id)).filter(models.Comment.post_id == post.id).scalar()
    )
    return PostOut(
        id=post.id,
        body=post.body,
        created_at=post.created_at,
        author=author,
        like_count=like_count,
        comment_count=comment_count,
    )


@router.get("", response_model=list[PostOut])
def list_posts(
    cursor: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(models.Post).order_by(models.Post.id.desc())
    if cursor is not None:
        query = query.filter(models.Post.id < cursor)
    posts = query.limit(limit).all()
    return [_to_post_out(db, post) for post in posts]


@router.post("", response_model=PostOut)
def create_post(payload: PostCreate, db: Session = Depends(get_db)):
    normalized = payload.username.strip().lower()
    author = db.query(models.User).filter(models.User.username == normalized).first()
    if author is None:
        raise HTTPException(status_code=404, detail="User not found.")

    post = models.Post(user_id=author.id, body=payload.body)
    db.add(post)
    db.commit()
    db.refresh(post)

    if not author.is_bot:
        enqueue_reactions_for_post(db, post)

    return _to_post_out(db, post)
