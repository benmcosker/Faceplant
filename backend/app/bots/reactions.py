import logging
import random
from datetime import datetime, timedelta

from anthropic import Anthropic
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import SessionLocal
from .roster import ROSTER

logger = logging.getLogger(__name__)

_client: Anthropic | None = None

_VOICE_NOTES_BY_USERNAME = {entry["username"]: entry.get("voice_notes") for entry in ROSTER}

THREAD_CONTEXT_LIMIT = 5


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def enqueue_reactions_for_post(db: Session, post: models.Post) -> None:
    """Schedules two waves of in-persona bot reactions to a human's new post."""
    bots = db.query(models.User).filter(models.User.is_bot.is_(True)).all()
    if not bots:
        return

    short_size = random.randint(settings.short_wave_size_min, settings.short_wave_size_max)
    long_size = random.randint(settings.long_wave_size_min, settings.long_wave_size_max)

    pool = bots[:]
    random.shuffle(pool)
    short_wave = pool[:short_size]
    remaining = pool[short_size:]
    long_wave = (
        remaining[:long_size]
        if len(remaining) >= long_size
        else random.sample(bots, min(long_size, len(bots)))
    )

    now = datetime.utcnow()
    for bot in short_wave:
        offset = timedelta(minutes=random.uniform(0, settings.short_reaction_window_minutes))
        db.add(
            models.BotReactionJob(post_id=post.id, bot_user_id=bot.id, scheduled_for=now + offset)
        )
    for bot in long_wave:
        offset = timedelta(
            minutes=random.uniform(
                settings.long_reaction_window_min_minutes,
                settings.long_reaction_window_max_minutes,
            )
        )
        db.add(
            models.BotReactionJob(post_id=post.id, bot_user_id=bot.id, scheduled_for=now + offset)
        )
    db.commit()


def _build_system_prompt(bot: models.User) -> str:
    system = (
        "You are role-playing a social media persona in the comments section of "
        f"a post. Persona: {bot.persona}"
    )
    voice_notes = _VOICE_NOTES_BY_USERNAME.get(bot.username)
    if voice_notes:
        system += f"\n\nVoice notes (style cues to follow closely): {voice_notes}"
    system += (
        "\n\nStay fully in character at all times. Write a single short, "
        "in-character reply (1-2 sentences, no hashtags, no surrounding "
        "quotation marks)."
    )
    return system


def _build_user_prompt(post: models.Post, thread_comments: list[tuple[str, str]]) -> str:
    parts = [f'Someone just posted:\n"""\n{post.body}\n"""']
    if thread_comments:
        thread = "\n".join(f"{username}: {body}" for username, body in thread_comments)
        parts.append(f"Recent replies already in the thread:\n{thread}")
    parts.append("Write your in-character reply to the post (and thread, if relevant).")
    return "\n\n".join(parts)


def _get_recent_comments(db: Session, post_id: int, limit: int = THREAD_CONTEXT_LIMIT) -> list[tuple[str, str]]:
    rows = (
        db.query(models.Comment, models.User.username)
        .join(models.User, models.Comment.user_id == models.User.id)
        .filter(models.Comment.post_id == post_id)
        .order_by(models.Comment.id.desc())
        .limit(limit)
        .all()
    )
    return [(username, comment.body) for comment, username in reversed(rows)]


def _generate_reaction_text(
    bot: models.User, post: models.Post, thread_comments: list[tuple[str, str]] | None = None
) -> str:
    client = _get_client()
    response = client.messages.create(
        model=bot.bot_model or settings.default_bot_model,
        max_tokens=160,
        system=_build_system_prompt(bot),
        messages=[{"role": "user", "content": _build_user_prompt(post, thread_comments or [])}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def run_due_reaction_jobs() -> None:
    """Polled every ~20s by the scheduler: executes any due, pending reaction jobs."""
    db = SessionLocal()
    try:
        due_jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.status == "pending")
            .filter(models.BotReactionJob.scheduled_for <= datetime.utcnow())
            .all()
        )
        for job in due_jobs:
            bot = db.get(models.User, job.bot_user_id)
            post = db.get(models.Post, job.post_id)
            if bot is None or post is None:
                job.status = "failed"
                job.executed_at = datetime.utcnow()
                db.commit()
                continue
            try:
                thread_comments = _get_recent_comments(db, post.id)
                text = _generate_reaction_text(bot, post, thread_comments)
                if text:
                    db.add(models.Comment(post_id=post.id, user_id=bot.id, body=text))
                already_liked = (
                    db.query(models.Like)
                    .filter(models.Like.post_id == post.id, models.Like.user_id == bot.id)
                    .first()
                )
                if already_liked is None:
                    db.add(models.Like(post_id=post.id, user_id=bot.id))
                job.status = "done"
            except Exception:
                logger.exception("bot reaction job %s failed", job.id)
                job.status = "failed"
            job.executed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
