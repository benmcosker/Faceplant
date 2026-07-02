import json
import logging
import random
import re
from datetime import datetime, timedelta

import httpx
from anthropic import Anthropic
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import SessionLocal
from .roster import ROSTER

logger = logging.getLogger(__name__)

_client: Anthropic | None = None

_VOICE_NOTES_BY_USERNAME = {entry["username"]: entry.get("voice_notes") for entry in ROSTER}
_USES_GIPHY_BY_USERNAME = {
    entry["username"] for entry in ROSTER if entry.get("uses_giphy")
}

THREAD_CONTEXT_LIMIT = 5

GIPHY_RANDOM_URL = "https://api.giphy.com/v1/gifs/random"


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
    if bot.username in _USES_GIPHY_BY_USERNAME:
        return _generate_giphy_reaction_text(bot, post, thread_comments or [])
    client = _get_client()
    response = client.messages.create(
        model=bot.bot_model or settings.default_bot_model,
        max_tokens=160,
        system=_build_system_prompt(bot),
        messages=[{"role": "user", "content": _build_user_prompt(post, thread_comments or [])}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def _build_giphy_system_prompt(bot: models.User) -> str:
    system = (
        "You are role-playing a social media persona who reacts to posts with a "
        f"reaction GIF plus a tiny caption. Persona: {bot.persona}"
    )
    voice_notes = _VOICE_NOTES_BY_USERNAME.get(bot.username)
    if voice_notes:
        system += f"\n\nVoice notes (style cues to follow closely): {voice_notes}"
    system += (
        "\n\nStay fully in character. Respond with ONLY a single JSON object and "
        "nothing else — no markdown, no code fences, no commentary. Use exactly "
        'this shape: {"caption": "<a tiny in-character caption, a few words at '
        'most, no hashtags>", "tag": "<one to three words naming the reaction GIF '
        "to search for, e.g. 'eye roll', 'mic drop', 'facepalm', 'popcorn'>\"}."
    )
    return system


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_caption_and_tag(raw: str) -> tuple[str, str]:
    """Pulls caption/tag out of the model's reply, tolerating stray code fences."""
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        return "", ""
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return "", ""
    caption = str(data.get("caption") or "").strip()
    tag = str(data.get("tag") or "").strip()
    return caption, tag


def _fetch_giphy_gif_url(tag: str) -> str:
    """Fetches a random GIF URL from Giphy for `tag`; "" if unavailable."""
    if not settings.giphy_api_key:
        return ""
    response = httpx.get(
        GIPHY_RANDOM_URL,
        params={"api_key": settings.giphy_api_key, "tag": tag, "rating": "pg-13"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json().get("data") or {}
    # The random endpoint nests the canonical URL under images.original.url and
    # also exposes a legacy top-level image_url; prefer the former.
    original = (data.get("images") or {}).get("original") or {}
    return (original.get("url") or data.get("image_url") or "").strip()


def _generate_giphy_reaction_text(
    bot: models.User, post: models.Post, thread_comments: list[tuple[str, str]]
) -> str:
    """A GIF-first reaction: model picks a caption + tag, Giphy supplies the GIF.

    Returns a ``caption\\ngif_url`` body (the frontend renders the trailing URL
    as an inline image). Falls back to caption-only if no GIF is available.
    """
    client = _get_client()
    response = client.messages.create(
        model=bot.bot_model or settings.default_bot_model,
        max_tokens=160,
        system=_build_giphy_system_prompt(bot),
        messages=[{"role": "user", "content": _build_user_prompt(post, thread_comments)}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text").strip()
    caption, tag = _parse_caption_and_tag(raw)
    gif_url = _fetch_giphy_gif_url(tag) if tag else ""
    if gif_url:
        return f"{caption}\n{gif_url}" if caption else gif_url
    return caption


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
