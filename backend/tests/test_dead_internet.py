"""Phase 2 of the "dead internet" feature: bots reacting to bots.

The whole point of these tests is to prove the loop is *bounded* — it must
terminate, stay under the per-thread cap and generation depth, and halt entirely
when spend crosses the ceiling. Runaway growth here is unbounded Anthropic spend,
so "it terminates" is the load-bearing assertion.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app import models
from app.bots import reactions
from app.config import settings
from app.db import SessionLocal


def _claim_user(client, username, avatar_file):
    return client.post("/api/users", data={"username": username}, files={"avatar": avatar_file}).json()


def _create_bot(client, admin_headers, username):
    return client.post(
        "/api/admin/bots",
        json={
            "username": username,
            "password": "password123",
            "persona": "an obvious bot",
            "avatar_url": "/media/avatars/placeholder.png",
        },
        headers=admin_headers,
    ).json()


def _fake_response():
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="beep boop fellow humans")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


def _make_due(post_id):
    db = SessionLocal()
    try:
        pending = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.post_id == post_id, models.BotReactionJob.status == "pending")
            .all()
        )
        for j in pending:
            j.scheduled_for = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()


def _drain(post_id, max_ticks=50):
    """Repeatedly make pending jobs due and run the worker until nothing is left.

    Raises if it doesn't settle within max_ticks — that's the runaway-loop tripwire.
    """
    for tick in range(max_ticks):
        db = SessionLocal()
        try:
            pending = (
                db.query(models.BotReactionJob)
                .filter(
                    models.BotReactionJob.post_id == post_id,
                    models.BotReactionJob.status == "pending",
                )
                .count()
            )
        finally:
            db.close()
        if pending == 0:
            return tick
        _make_due(post_id)
        with patch.object(reactions, "_get_client") as mock:
            mock.return_value.messages.create.return_value = _fake_response()
            reactions.run_due_reaction_jobs()
    raise AssertionError("reaction jobs never terminated — possible runaway loop")


def test_bot_to_bot_loop_is_bounded(client, avatar_file, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "bots_react_to_bots", True)
    for i in range(20):
        _create_bot(client, admin_headers, f"loopbot{i}")
    _claim_user(client, "seedhuman", avatar_file)
    post = client.post("/api/posts", json={"username": "seedhuman", "body": "kick it off"}).json()

    _drain(post["id"])  # raises if it never settles

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        gens = {j.generation for j in jobs}
        # Bounded on every axis: total count, generation depth, and it terminated.
        assert len(jobs) <= settings.max_reactions_per_thread
        assert max(gens) <= settings.max_reaction_generation
        assert all(j.status in ("done", "failed", "skipped") for j in jobs)
        # ...and the loop actually happened: bots reacted to bots at least one deep.
        assert max(gens) >= 1
    finally:
        db.close()


def test_loop_off_by_default_spawns_no_generations(client, avatar_file, admin_headers):
    # bots_react_to_bots defaults False — the normal swarm runs, but nothing deeper.
    for i in range(6):
        _create_bot(client, admin_headers, f"offbot{i}")
    _claim_user(client, "offhuman", avatar_file)
    post = client.post("/api/posts", json={"username": "offhuman", "body": "no loop please"}).json()

    _drain(post["id"])

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        assert jobs, "expected the normal gen-0 swarm"
        assert all(j.generation == 0 for j in jobs)  # no bot-to-bot generations
    finally:
        db.close()


def test_spend_ceiling_halts_reactions(client, avatar_file, admin_headers, monkeypatch):
    _create_bot(client, admin_headers, "ceilingbot")
    _claim_user(client, "ceilhuman", avatar_file)
    post = client.post("/api/posts", json={"username": "ceilhuman", "body": "too pricey"}).json()

    # Pretend the meter has already blown past a tiny ceiling.
    monkeypatch.setattr(settings, "global_spend_ceiling_usd", 0.01)
    db = SessionLocal()
    try:
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5", cost_usd=1.0))
        db.commit()
    finally:
        db.close()

    _make_due(post["id"])
    with patch.object(reactions, "_get_client") as mock:
        mock.return_value.messages.create.return_value = _fake_response()
        reactions.run_due_reaction_jobs()
        # Paused before any call: no Claude spend, no comment.
        mock.return_value.messages.create.assert_not_called()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        assert jobs and all(j.status == "skipped" for j in jobs)
        comments = db.query(models.Comment).filter(models.Comment.post_id == post["id"]).all()
        assert comments == []
    finally:
        db.close()


def test_bot_post_triggers_swarm_only_when_loop_on(client, avatar_file, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "bots_react_to_bots", True)
    _create_bot(client, admin_headers, "posterbot")
    _create_bot(client, admin_headers, "reactorbot1")
    _create_bot(client, admin_headers, "reactorbot2")

    post = client.post("/api/posts", json={"username": "posterbot", "body": "beep from a bot"}).json()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        # A bot-authored post now seeds a swarm — a thread with no human in it.
        assert len(jobs) > 0
        assert all(j.generation == 0 for j in jobs)
    finally:
        db.close()
