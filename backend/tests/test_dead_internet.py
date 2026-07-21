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
from app.bots import origination, reactions
from app.config import settings
from app.db import SessionLocal


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


def test_bot_to_bot_loop_is_bounded(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "bots_react_to_bots", True)
    for i in range(20):
        _create_bot(client, admin_headers, f"loopbot{i}")
    login("seedhuman@example.com", "seedhuman")
    post = client.post("/api/posts", json={"body": "kick it off"}).json()

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


def test_loop_off_by_default_spawns_no_generations(client, login, admin_headers):
    # bots_react_to_bots defaults False — the normal swarm runs, but nothing deeper.
    for i in range(6):
        _create_bot(client, admin_headers, f"offbot{i}")
    login("offhuman@example.com", "offhuman")
    post = client.post("/api/posts", json={"body": "no loop please"}).json()

    _drain(post["id"])

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        assert jobs, "expected the normal gen-0 swarm"
        assert all(j.generation == 0 for j in jobs)  # no bot-to-bot generations
    finally:
        db.close()


def test_spend_ceiling_halts_reactions(client, login, admin_headers, monkeypatch):
    _create_bot(client, admin_headers, "ceilingbot")
    login("ceilhuman@example.com", "ceilhuman")
    post = client.post("/api/posts", json={"body": "too pricey"}).json()

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


# --- Phase 3: autonomous bot origination + the "nobody" cost bucket ----------


def _bot_post_response(text="an unprompted bot thought"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=12, output_tokens=6),
    )


def _bot_posts(db):
    return (
        db.query(models.Post)
        .join(models.User, models.Post.user_id == models.User.id)
        .filter(models.User.is_bot.is_(True))
        .all()
    )


def test_bot_origination_creates_post_and_swarm_when_enabled(client, avatar_file, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "bot_origination_enabled", True)
    for i in range(4):
        _create_bot(client, admin_headers, f"origbot{i}")

    with patch.object(origination, "_get_client") as mock:
        mock.return_value.messages.create.return_value = _bot_post_response("beep. thoughts on oat milk.")
        origination.run_bot_origination()

    db = SessionLocal()
    try:
        posts = _bot_posts(db)
        assert len(posts) == 1
        assert posts[0].body == "beep. thoughts on oat milk."
        # The bot's post got swarmed — a thread with no human in it.
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == posts[0].id).all()
        assert len(jobs) > 0
        # Its spend is recorded as nobody's: source bot_post, no human attribution.
        rows = db.query(models.TokenUsage).filter(models.TokenUsage.source == "bot_post").all()
        assert len(rows) == 1 and rows[0].human_user_id is None
    finally:
        db.close()


def test_bot_origination_is_a_noop_when_disabled(client, avatar_file, admin_headers):
    _create_bot(client, admin_headers, "quietbot")
    origination.run_bot_origination()  # flag off by default

    db = SessionLocal()
    try:
        assert db.query(models.Post).count() == 0
    finally:
        db.close()


def test_bot_origination_is_rate_limited(client, avatar_file, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "bot_origination_enabled", True)
    for i in range(4):
        _create_bot(client, admin_headers, f"ratebot{i}")

    with patch.object(origination, "_get_client") as mock:
        mock.return_value.messages.create.return_value = _bot_post_response()
        origination.run_bot_origination()
        origination.run_bot_origination()  # immediately again — inside the interval

    db = SessionLocal()
    try:
        assert len(_bot_posts(db)) == 1  # only one bot post, not two
    finally:
        db.close()


def test_costs_folds_human_less_spend_into_nobody(client, login, admin_headers):
    login("realhuman@example.com", "realhuman")
    _create_bot(client, admin_headers, "voidbot")

    db = SessionLocal()
    try:
        human = db.query(models.User).filter(models.User.username == "realhuman").first()
        bot = db.query(models.User).filter(models.User.username == "voidbot").first()
        # served a human
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5", cost_usd=0.003, human_user_id=human.id))
        # a bot's own post being swarmed — attributed to a bot, i.e. nobody
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5", cost_usd=0.002, human_user_id=bot.id))
        # a bot post — no attribution at all
        db.add(models.TokenUsage(source="bot_post", model="claude-haiku-4-5", cost_usd=0.001, human_user_id=None))
        db.commit()
    finally:
        db.close()

    body = client.get("/api/costs").json()
    assert body["no_human_calls"] == 2
    assert body["no_human_cost_usd"] == 0.003  # 0.002 (bot-attributed) + 0.001 (bot post)
    # The per-human rollup stays humans-only.
    assert body["human_user_count"] == 1
    assert [u["username"] for u in body["per_human_user"]] == ["realhuman"]
