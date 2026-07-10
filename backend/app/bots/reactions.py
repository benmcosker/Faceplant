import json
import logging
import random
import re
from datetime import datetime, timedelta

from anthropic import Anthropic
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import giphy, models, usage
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


# --- "Dead internet": bots reacting to bots ---------------------------------
#
# All of the following is a no-op unless settings.bots_react_to_bots is on. It's
# what lets a thread keep growing after the humans leave — and every reaction is
# a real, metered Claude call, so it is bounded on three independent axes:
# generation depth, a per-thread cap, and a global spend ceiling kill-switch.


def _wave_size(generation: int) -> int:
    """Decaying wave size, so each successive bot-to-bot generation is smaller
    than the last and the thread tapers instead of exploding."""
    return max(1, settings.short_wave_size_min - generation)


def _thread_reaction_count(db: Session, post_id: int) -> int:
    """How many bot reactions have been scheduled for a thread (the per-thread cap)."""
    return (
        db.query(func.count(models.BotReactionJob.id))
        .filter(models.BotReactionJob.post_id == post_id)
        .scalar()
    ) or 0


def _reactions_paused(db: Session) -> bool:
    """Global kill-switch: halt all bot reactions once cumulative metered spend
    crosses the ceiling. The last line of defense against an unbounded bill for a
    conversation nobody is having."""
    ceiling = settings.global_spend_ceiling_usd
    if ceiling <= 0:
        return False
    total = db.query(func.coalesce(func.sum(models.TokenUsage.cost_usd), 0.0)).scalar() or 0.0
    return total >= ceiling


def _uncommented_bots(db: Session, post_id: int) -> list[models.User]:
    """Bots that haven't already replied to this thread — keeps successive waves
    varied and naturally bounds growth as the pool of fresh voices runs dry."""
    commented_ids = {
        row[0]
        for row in db.query(models.Comment.user_id).filter(models.Comment.post_id == post_id).all()
    }
    bots = db.query(models.User).filter(models.User.is_bot.is_(True)).all()
    return [b for b in bots if b.id not in commented_ids]


def _maybe_spawn_next_generation(db: Session, post: models.Post, current_generation: int) -> None:
    """After a bot reaction, schedule a smaller next-generation wave so bots reply
    to bots and the thread sustains itself. Bounded by max_reaction_generation, the
    per-thread cap, and the spend ceiling. Enqueued once per generation per post."""
    if not settings.bots_react_to_bots:
        return
    next_gen = current_generation + 1
    if next_gen > settings.max_reaction_generation:
        return
    if _thread_reaction_count(db, post.id) >= settings.max_reactions_per_thread:
        return
    if _reactions_paused(db):
        return
    # Only the first job of a generation seeds the next wave — otherwise every
    # reaction in a wave would pile on its own wave and growth would explode.
    already = (
        db.query(models.BotReactionJob.id)
        .filter(
            models.BotReactionJob.post_id == post.id,
            models.BotReactionJob.generation == next_gen,
        )
        .first()
    )
    if already:
        return
    candidates = _uncommented_bots(db, post.id)
    if not candidates:
        return
    size = min(_wave_size(next_gen), len(candidates))
    now = datetime.utcnow()
    for bot in random.sample(candidates, size):
        offset = timedelta(minutes=random.uniform(0, settings.short_reaction_window_minutes))
        db.add(
            models.BotReactionJob(
                post_id=post.id,
                bot_user_id=bot.id,
                scheduled_for=now + offset,
                generation=next_gen,
            )
        )


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
):
    """Returns (reply_text, api_response). The response carries token usage for
    the cost meter; it's None only if no API call was made."""
    if bot.username in _USES_GIPHY_BY_USERNAME:
        return _generate_giphy_reaction_text(bot, post, thread_comments or [])
    client = _get_client()
    response = client.messages.create(
        model=bot.bot_model or settings.default_bot_model,
        max_tokens=160,
        system=_build_system_prompt(bot),
        messages=[{"role": "user", "content": _build_user_prompt(post, thread_comments or [])}],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text, response


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


def _generate_giphy_reaction_text(
    bot: models.User, post: models.Post, thread_comments: list[tuple[str, str]]
):
    """A GIF-first reaction: model picks a caption + tag, Giphy supplies the GIF.

    Returns ``(caption\\ngif_url, api_response)`` (the frontend renders the
    trailing URL as an inline image). Falls back to caption-only if no GIF is
    available. The response carries token usage for the cost meter.
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
    gif_url = giphy.fetch_random_gif_url(tag) if tag else ""
    if gif_url:
        text = f"{caption}\n{gif_url}" if caption else gif_url
    else:
        text = caption
    return text, response


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
            # Global spend kill-switch: once the meter crosses the ceiling, stop
            # spending — skip the job instead of making another Claude call.
            if _reactions_paused(db):
                job.status = "skipped"
                job.executed_at = datetime.utcnow()
                db.commit()
                continue
            try:
                thread_comments = _get_recent_comments(db, post.id)
                text, response = _generate_reaction_text(bot, post, thread_comments)
                if text:
                    db.add(models.Comment(post_id=post.id, user_id=bot.id, body=text))
                # Meter the tokens this reaction spent, attributed to the human
                # whose post the swarm is reacting to.
                if response is not None:
                    usage.record(
                        db,
                        source="bot_reaction",
                        model=bot.bot_model or settings.default_bot_model,
                        response=response,
                        human_user_id=post.user_id,
                        post_id=post.id,
                        actor=bot.username,
                    )
                already_liked = (
                    db.query(models.Like)
                    .filter(models.Like.post_id == post.id, models.Like.user_id == bot.id)
                    .first()
                )
                if already_liked is None:
                    db.add(models.Like(post_id=post.id, user_id=bot.id))
                job.status = "done"
                # Bots reacting to bots: schedule a smaller next-generation wave,
                # so the thread keeps talking to itself after the humans leave.
                _maybe_spawn_next_generation(db, post, job.generation)
            except Exception:
                logger.exception("bot reaction job %s failed", job.id)
                job.status = "failed"
            job.executed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
