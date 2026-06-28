from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..schemas import CommentCreate, CommentOut

router = APIRouter(prefix="/api/posts", tags=["comments"])


@router.get("/{post_id}/comments", response_model=list[CommentOut])
def list_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    comments = (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post_id)
        .order_by(models.Comment.id.asc())
        .all()
    )
    return [
        CommentOut(
            id=c.id,
            body=c.body,
            created_at=c.created_at,
            author=db.get(models.User, c.user_id),
        )
        for c in comments
    ]


@router.post("/{post_id}/comments", response_model=CommentOut)
def add_comment(post_id: int, payload: CommentCreate, db: Session = Depends(get_db)):
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    normalized = payload.username.strip().lower()
    author = db.query(models.User).filter(models.User.username == normalized).first()
    if author is None:
        raise HTTPException(status_code=404, detail="User not found.")

    comment = models.Comment(post_id=post_id, user_id=author.id, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentOut(id=comment.id, body=comment.body, created_at=comment.created_at, author=author)
