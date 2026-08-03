"""Tests for the shared-house-style prompt-caching path.

When settings.use_prompt_caching is on, every reaction's `system` gains a large,
byte-identical house-style block marked for caching, sent ahead of the per-bot
persona. These tests assert the system is shaped correctly in both the sync and
batch paths, that it stays a plain string when the flag is off, that the shared
block is big enough to actually cache on the default model, and that The Meter
prices cache reads/writes.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app import models, usage
from app.bots import reactions
from app.bots.house_style import HOUSE_STYLE_GUIDE
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


def _make_jobs_due(post_id, bot_username):
    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == bot_username).first()
        jobs = (
            db.query(models.BotReactionJob)
            .filter(
                models.BotReactionJob.post_id == post_id,
                models.BotReactionJob.bot_user_id == bot.id,
            )
            .all()
        )
        for job in jobs:
            job.scheduled_for = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
        return [j.id for j in jobs]
    finally:
        db.close()


def test_house_style_guide_clears_haiku_cache_floor():
    # The default bot model (claude-haiku-4-5) only caches prefixes of >= 4096
    # tokens; below that, a cache_control marker is silently ignored. Char count is
    # a proxy for tokens (~4 chars/token) — this guard keeps an edit from quietly
    # shrinking the shared block below the floor and turning caching into a no-op.
    assert len(HOUSE_STYLE_GUIDE) >= 16400


def test_caching_off_keeps_system_a_plain_string(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_prompt_caching", False)
    _create_bot(client, admin_headers, "plainbot")
    login("plainhuman@example.com", "plainhuman")
    post = client.post("/api/posts", json={"body": "no cache here"}).json()
    _make_jobs_due(post["id"], "plainbot")

    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="plain reaction")],
        usage=SimpleNamespace(input_tokens=50, output_tokens=20),
    )
    with patch.object(reactions, "_get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = fake_response
        reactions.run_due_reaction_jobs()

    system = mock_get_client.return_value.messages.create.call_args.kwargs["system"]
    assert isinstance(system, str)
    assert "an obvious bot" in system
    assert HOUSE_STYLE_GUIDE not in system


def test_caching_on_prepends_cached_house_style_block(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_prompt_caching", True)
    _create_bot(client, admin_headers, "cachebot")
    login("cachehuman@example.com", "cachehuman")
    post = client.post("/api/posts", json={"body": "cache this one"}).json()
    _make_jobs_due(post["id"], "cachebot")

    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="cached-path reaction")],
        usage=SimpleNamespace(input_tokens=40, output_tokens=15),
    )
    with patch.object(reactions, "_get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = fake_response
        reactions.run_due_reaction_jobs()

    system = mock_get_client.return_value.messages.create.call_args.kwargs["system"]
    assert isinstance(system, list) and len(system) == 2
    # Block 0: the shared house-style guide, marked for caching.
    assert system[0]["type"] == "text"
    assert system[0]["text"] == HOUSE_STYLE_GUIDE
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    # Block 1: the per-bot persona (unchanged, uncached).
    assert system[1]["type"] == "text"
    assert "an obvious bot" in system[1]["text"]
    assert "cache_control" not in system[1]

    # The reaction still lands: comment written, cost metered.
    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "cachebot").first()
        assert db.query(models.Comment).filter(
            models.Comment.post_id == post["id"], models.Comment.user_id == bot.id
        ).count() >= 1
    finally:
        db.close()


def test_caching_on_in_batch_submit(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_prompt_caching", True)
    monkeypatch.setattr(settings, "use_batch_api", True)
    _create_bot(client, admin_headers, "cachebatchbot")
    login("cachebatchhuman@example.com", "cachebatchhuman")
    post = client.post("/api/posts", json={"body": "cached and batched"}).json()
    _make_jobs_due(post["id"], "cachebatchbot")

    with patch.object(reactions, "_get_client") as mock_get_client:
        batches = mock_get_client.return_value.beta.messages.batches
        batches.create.return_value = SimpleNamespace(id="msgbatch_cache")
        reactions.run_due_reaction_jobs()  # submit

    requests = batches.create.call_args.kwargs["requests"]
    assert requests
    for req in requests:
        system = req["params"]["system"]
        assert isinstance(system, list) and len(system) == 2
        assert system[0]["text"] == HOUSE_STYLE_GUIDE
        assert system[0]["cache_control"] == {"type": "ephemeral"}
        assert "an obvious bot" in system[1]["text"]


def test_cost_usd_prices_cache_reads_and_writes():
    # claude-haiku-4-5 input price is $1/MTok. A cache read is ~0.1x, a write ~1.25x.
    base = usage.cost_usd("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=0)
    assert base == 1.0
    read = usage.cost_usd(
        "claude-haiku-4-5", input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000
    )
    assert read == 0.10
    write = usage.cost_usd(
        "claude-haiku-4-5", input_tokens=0, output_tokens=0, cache_creation_tokens=1_000_000
    )
    assert write == 1.25


def test_meter_records_discounted_cost_on_cache_hit(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_prompt_caching", True)
    _create_bot(client, admin_headers, "metercachebot")
    login("metercachehuman@example.com", "metercachehuman")
    post = client.post("/api/posts", json={"body": "meter the cache"}).json()
    _make_jobs_due(post["id"], "metercachebot")

    # A response that read a big cached prefix: 4000 cache-read tokens billed at 0.1x.
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="cache-hit reaction")],
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=20,
            cache_read_input_tokens=4000,
            cache_creation_input_tokens=0,
        ),
    )
    with patch.object(reactions, "_get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = fake_response
        reactions.run_due_reaction_jobs()

    expected = usage.cost_usd(
        "claude-haiku-4-5", input_tokens=50, output_tokens=20, cache_read_tokens=4000
    )
    db = SessionLocal()
    try:
        rows = db.query(models.TokenUsage).filter(models.TokenUsage.source == "bot_reaction").all()
        assert rows
        # Every reaction row reflects the cache-read discount, not full input price.
        for r in rows:
            assert abs(r.cost_usd - expected) < 1e-12
    finally:
        db.close()
