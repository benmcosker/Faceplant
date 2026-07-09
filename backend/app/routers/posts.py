from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..ads.targeting import classify_mood
from ..bots.reactions import enqueue_reactions_for_post
from ..db import get_db
from ..schemas import CommentOut, PostCreate, PostOut

router = APIRouter(prefix="/api/posts", tags=["posts"])

# How many replies to inline as a "peek" under each post in the feed.
PEEK_COMMENTS = 2


def _to_post_out(db: Session, post: models.Post) -> PostOut:
    author = db.get(models.User, post.user_id)
    like_count = db.query(func.count(models.Like.id)).filter(models.Like.post_id == post.id).scalar()
    comment_count = (
        db.query(func.count(models.Comment.id)).filter(models.Comment.post_id == post.id).scalar()
    )
    # The earliest replies (thread order), so the swarm is visible without a click.
    peek = (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post.id)
        .order_by(models.Comment.id.asc())
        .limit(PEEK_COMMENTS)
        .all()
    )
    top_comments = [
        CommentOut(
            id=c.id,
            body=c.body,
            created_at=c.created_at,
            author=db.get(models.User, c.user_id),
        )
        for c in peek
    ]
    return PostOut(
        id=post.id,
        body=post.body,
        created_at=post.created_at,
        author=author,
        like_count=like_count,
        comment_count=comment_count,
        top_comments=top_comments,
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

    if not author.is_bot:
        # The platform profiles the emotional tone of what you just posted and
        # remembers it, so it can target "sponsored" content at your mood.
        author.mood = classify_mood(payload.body)

    db.commit()
    db.refresh(post)

    if not author.is_bot:
        enqueue_reactions_for_post(db, post)

    return _to_post_out(db, post)
