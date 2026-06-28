import logging
import random
from datetime import datetime, timedelta

from anthropic import Anthropic
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import SessionLocal

logger = logging.getLogger(__name__)

_client: Anthropic | None = None


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


def _build_prompt(bot: models.User, post: models.Post) -> str:
    return (
        f"You are role-playing a social media persona: {bot.persona}\n\n"
        f'Someone just posted:\n"""\n{post.body}\n"""\n\n'
        "Write a single short, in-character reply (1-2 sentences, no hashtags, no "
        "surrounding quotation marks). Stay fully in character."
    )


def _generate_reaction_text(bot: models.User, post: models.Post) -> str:
    client = _get_client()
    response = client.messages.create(
        model=bot.bot_model or settings.default_bot_model,
        max_tokens=120,
        messages=[{"role": "user", "content": _build_prompt(bot, post)}],
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
                text = _generate_reaction_text(bot, post)
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
