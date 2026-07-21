import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import giphy, models
from ..auth import get_current_user
from ..db import get_db
from ..schemas import CommentCreate, CommentOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/posts", tags=["comments"])

# A Slack-style slash command: a comment of `/giphy <keyword>` is replaced with
# a matching GIF from Giphy, which the frontend renders inline as an image.
_GIPHY_COMMAND_RE = re.compile(r"^/giphy\s+(.+)$", re.IGNORECASE | re.DOTALL)


def _resolve_giphy_command(body: str) -> str:
    """If `body` is a `/giphy <keyword>` command, swap it for a matching GIF URL.

    Leaves the body untouched when it isn't the command, and falls back to the
    literal text the user typed if Giphy is unavailable (no key, no match, or a
    request error) so a comment is never silently dropped.
    """
    match = _GIPHY_COMMAND_RE.match(body.strip())
    if not match:
        return body
    keyword = match.group(1).strip()
    try:
        gif_url = giphy.search_gif_url(keyword)
    except Exception:
        logger.exception("giphy command lookup failed for %r", keyword)
        gif_url = ""
    return gif_url or body


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
def add_comment(
    post_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    author: models.User = Depends(get_current_user),
):
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    comment = models.Comment(
        post_id=post_id, user_id=author.id, body=_resolve_giphy_command(payload.body)
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentOut(id=comment.id, body=comment.body, created_at=comment.created_at, author=author)
