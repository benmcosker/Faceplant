from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..ads.targeting import classify_mood
from ..bots.reactions import enqueue_reactions_for_post
from ..config import settings
from ..db import get_db
from ..schemas import CommentOut, PostCreate, PostOut, ThreadStats

router = APIRouter(prefix="/api/posts", tags=["posts"])

# How many replies to inline as a "peek" under each post in the feed.
PEEK_COMMENTS = 2


def _thread_humanity(
    db: Session, post: models.Post, author: models.User, comment_count: int
) -> ThreadStats:
    """How human a thread is, by message count (the post + its comments).

    A human post with a bot pile-on trends toward 0% human — the "dead internet"
    counter. Measured by message, so reply volume (not just participants) drives
    it down.
    """
    bot_comment_count = (
        db.query(func.count(models.Comment.id))
        .join(models.User, models.Comment.user_id == models.User.id)
        .filter(models.Comment.post_id == post.id, models.User.is_bot.is_(True))
        .scalar()
    ) or 0
    human_comment_count = comment_count - bot_comment_count
    human_messages = (0 if author.is_bot else 1) + human_comment_count
    total_messages = 1 + comment_count  # the post itself is one message
    bot_messages = total_messages - human_messages
    human_share = round(human_messages / total_messages, 4) if total_messages else 1.0
    return ThreadStats(
        human_share=human_share,
        human_messages=human_messages,
        bot_messages=bot_messages,
        total_messages=total_messages,
    )


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
    humanity = _thread_humanity(db, post, author, comment_count)
    return PostOut(
        id=post.id,
        body=post.body,
        created_at=post.created_at,
        author=author,
        like_count=like_count,
        comment_count=comment_count,
        top_comments=top_comments,
        human_share=humanity.human_share,
        human_messages=humanity.human_messages,
        bot_messages=humanity.bot_messages,
        total_messages=humanity.total_messages,
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


@router.get("/{post_id}/thread-stats", response_model=ThreadStats)
def thread_stats(post_id: int, db: Session = Depends(get_db)):
    """Live "% human" for one thread — polled by the frontend as bots pile on."""
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    author = db.get(models.User, post.user_id)
    comment_count = (
        db.query(func.count(models.Comment.id)).filter(models.Comment.post_id == post_id).scalar()
    ) or 0
    return _thread_humanity(db, post, author, comment_count)


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

    # Human posts always get swarmed. Bot-authored posts do too, but only once
    # the "dead internet" loop is switched on — so a thread can start with no
    # human in it at all.
    if not author.is_bot or settings.bots_react_to_bots:
        enqueue_reactions_for_post(db, post)

    return _to_post_out(db, post)
