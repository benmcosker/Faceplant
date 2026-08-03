import json
import logging
import random
import re
from datetime import datetime, timedelta

from anthropic import Anthropic
# Message Batches on the pinned anthropic==0.40.0 SDK lives under the `beta`
# namespace (client.beta.messages.batches); the request/param types come from
# the matching beta modules. Functionally it's the same 50%-off batch API.
from anthropic.types.beta.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.beta.messages.batch_create_params import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import giphy, models, usage
from ..config import settings
from ..db import SessionLocal
from .house_style import HOUSE_STYLE_GUIDE
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


def _persona_system_prompt(bot: models.User) -> str:
    """The persona system prompt — GIF-first bots get the caption+tag JSON prompt."""
    if bot.username in _USES_GIPHY_BY_USERNAME:
        return _build_giphy_system_prompt(bot)
    return _build_system_prompt(bot)


def _system_param_for(bot: models.User):
    """The `system` value to send for this bot's reaction.

    With caching off (the default) this is the plain persona string — byte-for-byte
    what it has always been. With settings.use_prompt_caching on, it becomes a list
    of two blocks: the large, shared house-style guide first, marked for caching so
    repeat reactions read it cheaply, then the per-bot persona block (unchanged) after
    the breakpoint. The shared block must stay identical across every request or the
    cached prefix is invalidated — which is why the persona lives in its own block.
    """
    persona = _persona_system_prompt(bot)
    if not settings.use_prompt_caching:
        return persona
    return [
        {
            "type": "text",
            "text": HOUSE_STYLE_GUIDE,
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": persona},
    ]


def _decode_reaction_text(bot: models.User, message) -> str:
    """Turns a completed Claude message into the comment body to post.

    Shared by the synchronous and batched paths. For GIF-first bots this parses
    the caption/tag JSON and resolves a Giphy URL (a synchronous fetch); everyone
    else just gets the model's plain text.
    """
    raw = "".join(block.text for block in message.content if block.type == "text").strip()
    if bot.username not in _USES_GIPHY_BY_USERNAME:
        return raw
    caption, tag = _parse_caption_and_tag(raw)
    gif_url = giphy.fetch_random_gif_url(tag) if tag else ""
    if gif_url:
        return f"{caption}\n{gif_url}" if caption else gif_url
    return caption


def _generate_reaction_text(
    bot: models.User, post: models.Post, thread_comments: list[tuple[str, str]] | None = None
):
    """Returns (reply_text, api_response). The response carries token usage for
    the cost meter; it's None only if no API call was made."""
    client = _get_client()
    response = client.messages.create(
        model=bot.bot_model or settings.default_bot_model,
        max_tokens=160,
        system=_system_param_for(bot),
        messages=[{"role": "user", "content": _build_user_prompt(post, thread_comments or [])}],
    )
    return _decode_reaction_text(bot, response), response


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


def _finalize_reaction(
    db: Session, job: models.BotReactionJob, bot: models.User, post: models.Post, text: str, response
) -> None:
    """Write the side effects of one completed reaction: the comment, the metered
    cost, the bot's like, mark the job done, and (if enabled) seed the next wave.

    Shared by the synchronous path and the batch-reconcile path so both produce
    identical results — only *when* the Claude call happens differs.
    """
    if text:
        db.add(models.Comment(post_id=post.id, user_id=bot.id, body=text))
    # Meter the tokens this reaction spent, attributed to the human whose post
    # the swarm is reacting to.
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
    # Bots reacting to bots: schedule a smaller next-generation wave, so the
    # thread keeps talking to itself after the humans leave.
    _maybe_spawn_next_generation(db, post, job.generation)


def run_due_reaction_jobs() -> None:
    """Polled every ~20s by the scheduler. Dispatches to the batched or synchronous
    path depending on settings.use_batch_api."""
    if settings.use_batch_api:
        _submit_due_reaction_batch()
    else:
        _run_due_reaction_jobs_sync()


def _run_due_reaction_jobs_sync() -> None:
    """One synchronous Claude call per due, pending reaction job."""
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
                _finalize_reaction(db, job, bot, post, text, response)
            except Exception:
                logger.exception("bot reaction job %s failed", job.id)
                job.status = "failed"
            job.executed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


# --- Batch API path ---------------------------------------------------------
#
# The reaction waves are already delayed by minutes to hours, so nothing is
# waiting on a live response — an ideal fit for the async Message Batches API,
# which runs the same calls for 50% of the price. Submission and reconciliation
# are two separate scheduler passes: _submit_due_reaction_batch collects the due
# jobs and posts them as one batch (jobs go "pending" -> "submitted"), and
# reconcile_reaction_batches later writes the results once the batch ends.


def _submit_due_reaction_batch() -> None:
    """Submit all due, pending reaction jobs as a single Message Batches job."""
    db = SessionLocal()
    try:
        due_jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.status == "pending")
            .filter(models.BotReactionJob.scheduled_for <= datetime.utcnow())
            .all()
        )
        if not due_jobs:
            return
        # Spend kill-switch, checked once at submit time: don't open a batch we
        # can't afford to reconcile.
        if _reactions_paused(db):
            for job in due_jobs:
                job.status = "skipped"
                job.executed_at = datetime.utcnow()
            db.commit()
            return

        requests: list[Request] = []
        batched_jobs: list[models.BotReactionJob] = []
        for job in due_jobs:
            bot = db.get(models.User, job.bot_user_id)
            post = db.get(models.Post, job.post_id)
            if bot is None or post is None:
                job.status = "failed"
                job.executed_at = datetime.utcnow()
                continue
            # Thread context is snapshotted at submit time and baked into the
            # prompt; the batch may not run for minutes.
            thread_comments = _get_recent_comments(db, post.id)
            requests.append(
                Request(
                    custom_id=str(job.id),
                    params=MessageCreateParamsNonStreaming(
                        model=bot.bot_model or settings.default_bot_model,
                        max_tokens=160,
                        system=_system_param_for(bot),
                        messages=[
                            {"role": "user", "content": _build_user_prompt(post, thread_comments)}
                        ],
                    ),
                )
            )
            batched_jobs.append(job)

        if not requests:
            db.commit()
            return

        try:
            batch = _get_client().beta.messages.batches.create(requests=requests)
        except Exception:
            logger.exception("failed to submit reaction batch (%d jobs)", len(requests))
            db.rollback()
            return

        for job in batched_jobs:
            job.status = "submitted"
            job.batch_id = batch.id
        db.add(
            models.ReactionBatch(
                anthropic_batch_id=batch.id, status="submitted", submitted_count=len(batched_jobs)
            )
        )
        db.commit()
    finally:
        db.close()


def reconcile_reaction_batches() -> None:
    """Polled by the scheduler. Fetches results for any batch that has finished
    and writes the reactions it carried. A no-op with no open batches, so it is
    harmless to run even when use_batch_api is off."""
    db = SessionLocal()
    try:
        open_batches = (
            db.query(models.ReactionBatch)
            .filter(models.ReactionBatch.status != "ended")
            .all()
        )
        if not open_batches:
            return
        client = _get_client()
        for rb in open_batches:
            try:
                remote = client.beta.messages.batches.retrieve(rb.anthropic_batch_id)
            except Exception:
                logger.exception("failed to retrieve batch %s", rb.anthropic_batch_id)
                continue
            if remote.processing_status != "ended":
                continue
            _apply_batch_results(db, client, rb)
    finally:
        db.close()


def _apply_batch_results(db: Session, client: Anthropic, rb: models.ReactionBatch) -> None:
    """Write the comments/likes/cost for every result in a finished batch, then
    mark the batch ended. Results arrive in any order, keyed by custom_id."""
    for result in client.beta.messages.batches.results(rb.anthropic_batch_id):
        try:
            job = db.get(models.BotReactionJob, int(result.custom_id))
        except (TypeError, ValueError):
            job = None
        # Skip anything already handled (a re-run after a partial reconcile).
        if job is None or job.status != "submitted":
            continue
        bot = db.get(models.User, job.bot_user_id)
        post = db.get(models.Post, job.post_id)
        if bot is None or post is None or result.result.type != "succeeded":
            job.status = "failed"
            job.executed_at = datetime.utcnow()
            db.commit()
            continue
        try:
            message = result.result.message
            text = _decode_reaction_text(bot, message)
            _finalize_reaction(db, job, bot, post, text, message)
        except Exception:
            logger.exception("failed to apply batch result for job %s", job.id)
            job.status = "failed"
        job.executed_at = datetime.utcnow()
        db.commit()

    rb.status = "ended"
    db.commit()
