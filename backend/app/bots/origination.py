"""Phase 3 of the "dead internet": bots posting on their own.

When enabled, a background job occasionally has an idle bot author an original
post — and then swarms it — so a thread can begin with no human in it at all.
Off by default, rate-limited, and halted by the same global spend ceiling as the
reaction loop, because a feed that writes itself also bills itself.
"""

import logging
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import models, usage
from ..config import settings
from ..db import SessionLocal
from .reactions import _get_client, _reactions_paused, enqueue_reactions_for_post
from .roster import ROSTER

logger = logging.getLogger(__name__)

_VOICE_NOTES_BY_USERNAME = {entry["username"]: entry.get("voice_notes") for entry in ROSTER}


def _build_post_system_prompt(bot: models.User) -> str:
    system = (
        "You are role-playing a social media persona writing an original post to "
        "your own feed — unprompted, whatever's on your mind right now. Persona: "
        f"{bot.persona}"
    )
    voice_notes = _VOICE_NOTES_BY_USERNAME.get(bot.username)
    if voice_notes:
        system += f"\n\nVoice notes (style cues to follow closely): {voice_notes}"
    system += (
        "\n\nStay fully in character. Write a single short, in-character original "
        "post (1-2 sentences, no hashtags, no surrounding quotation marks)."
    )
    return system


def _last_bot_post_at(db: Session) -> datetime | None:
    """When the most recent bot-authored post was made, for rate limiting."""
    row = (
        db.query(models.Post)
        .join(models.User, models.Post.user_id == models.User.id)
        .filter(models.User.is_bot.is_(True))
        .order_by(models.Post.created_at.desc())
        .first()
    )
    return row.created_at if row else None


def run_bot_origination() -> None:
    """Maybe have a bot author an original post and seed a swarm on it.

    A no-op unless bot_origination_enabled is on. Rate-limited to one bot post per
    bot_post_interval_minutes, and skipped entirely once metered spend crosses the
    ceiling — the spend with no human at either end still costs real money.
    """
    if not settings.bot_origination_enabled:
        return
    db = SessionLocal()
    try:
        if _reactions_paused(db):
            return
        last = _last_bot_post_at(db)
        if last is not None and datetime.utcnow() - last < timedelta(
            minutes=settings.bot_post_interval_minutes
        ):
            return
        bots = db.query(models.User).filter(models.User.is_bot.is_(True)).all()
        if not bots:
            return
        bot = random.choice(bots)
        try:
            client = _get_client()
            response = client.messages.create(
                model=bot.bot_model or settings.default_bot_model,
                max_tokens=160,
                system=_build_post_system_prompt(bot),
                messages=[{"role": "user", "content": "Write your original post now."}],
            )
            text = "".join(block.text for block in response.content if block.type == "text").strip()
            if not text:
                return
            post = models.Post(user_id=bot.id, body=text)
            db.add(post)
            db.commit()
            db.refresh(post)
            # Spend with no human at either end — attributed to nobody (human_user_id=None).
            usage.record(
                db,
                source="bot_post",
                model=bot.bot_model or settings.default_bot_model,
                response=response,
                human_user_id=None,
                post_id=post.id,
                actor=bot.username,
            )
            # Swarm the bot's post, so the thread fills with bots reacting to a bot.
            enqueue_reactions_for_post(db, post)
            db.commit()
        except Exception:
            logger.exception("bot origination failed")
            db.rollback()
    finally:
        db.close()
