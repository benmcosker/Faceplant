from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import models, usage
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


@pytest.mark.parametrize(
    "model,inp,out,expected",
    [
        ("claude-haiku-4-5", 1_000_000, 0, 1.0),
        ("claude-haiku-4-5", 0, 1_000_000, 5.0),
        ("claude-haiku-4-5", 1000, 200, 0.001 + 0.001),
        ("unknown-model", 1_000_000, 0, 1.0),  # falls back to default pricing
    ],
)
def test_cost_usd(model, inp, out, expected):
    assert usage.cost_usd(model, inp, out) == pytest.approx(expected)


def test_record_tolerates_missing_usage():
    # A response with no usage attribute records a zero-cost row, never raises.
    db = SessionLocal()
    try:
        row = usage.record(
            db,
            source="bot_reaction",
            model="claude-haiku-4-5",
            response=SimpleNamespace(content=[]),
            human_user_id=None,
            actor="somebot",
        )
        db.commit()
        assert row is not None
        assert row.input_tokens == 0 and row.output_tokens == 0 and row.cost_usd == 0.0
    finally:
        db.close()


def test_costs_endpoint_empty(client):
    res = client.get("/api/costs")
    assert res.status_code == 200
    body = res.json()
    assert body["total_cost_usd"] == 0.0
    assert body["total_calls"] == 0
    assert body["per_human_user"] == []
    assert body["cost_per_human_user_avg"] == 0.0
    # Phase 2 storytelling fields are present and empty-safe.
    assert body["cost_per_post_usd"] == 0.0
    assert body["rate_per_min_usd"] == 0.0
    assert body["recent"] == []
    assert body["spend_per_min"] == [0.0] * 15


def test_costs_endpoint_aggregates_and_attributes(client, avatar_file):
    human = _claim_user(client, "spender", avatar_file)
    db = SessionLocal()
    try:
        # Two bot reactions + one ad tagline, all triggered by one human.
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5",
                                 input_tokens=1000, output_tokens=200, cost_usd=0.002,
                                 human_user_id=human["id"], actor="botA"))
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5",
                                 input_tokens=1000, output_tokens=200, cost_usd=0.002,
                                 human_user_id=human["id"], actor="botB"))
        db.add(models.TokenUsage(source="ad_tagline", model="claude-haiku-4-5",
                                 input_tokens=500, output_tokens=40, cost_usd=0.0007,
                                 human_user_id=human["id"], actor="Evergreen Farewell Plans"))
        db.commit()
    finally:
        db.close()

    body = client.get("/api/costs").json()
    assert body["total_calls"] == 3
    assert body["total_cost_usd"] == pytest.approx(0.0047)
    assert body["by_source"]["bot_reaction"]["calls"] == 2
    assert body["by_source"]["ad_tagline"]["calls"] == 1
    # Per-human attribution + average.
    assert body["human_user_count"] == 1
    assert body["per_human_user"][0]["username"] == "spender"
    assert body["per_human_user"][0]["cost_usd"] == pytest.approx(0.0047)
    assert body["cost_per_human_user_avg"] == pytest.approx(0.0047)


def test_costs_endpoint_storytelling_layer(client, avatar_file):
    human = _claim_user(client, "storyteller", avatar_file)
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        # Two reactions on post 1, one on post 2 — all recent (this minute).
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5",
                                 input_tokens=1000, output_tokens=200, cost_usd=0.002,
                                 human_user_id=human["id"], post_id=1, actor="gifgremlin",
                                 created_at=now - timedelta(seconds=10)))
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5",
                                 input_tokens=1000, output_tokens=200, cost_usd=0.002,
                                 human_user_id=human["id"], post_id=1, actor="doomscroller",
                                 created_at=now - timedelta(seconds=5)))
        db.add(models.TokenUsage(source="ad_tagline", model="claude-haiku-4-5",
                                 input_tokens=500, output_tokens=40, cost_usd=0.0007,
                                 human_user_id=human["id"], post_id=2, actor="Evergreen Farewell Plans",
                                 created_at=now - timedelta(seconds=2)))
        # An older row (12 minutes ago) — counts toward totals + sparkline, not the $/min rate.
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5",
                                 input_tokens=1000, output_tokens=200, cost_usd=0.002,
                                 human_user_id=human["id"], post_id=3, actor="oldbot",
                                 created_at=now - timedelta(minutes=12)))
        db.commit()
    finally:
        db.close()

    body = client.get("/api/costs").json()

    # Cost per post: total 0.0067 across 3 distinct posts.
    assert body["cost_per_post_usd"] == pytest.approx(0.0067 / 3, abs=1e-6)
    # $/min rate: only the three sub-minute rows (0.002 + 0.002 + 0.0007).
    assert body["rate_per_min_usd"] == pytest.approx(0.0047)
    # Ticker: newest first, with actor + human resolved.
    assert len(body["recent"]) == 4
    assert body["recent"][0]["actor"] == "Evergreen Farewell Plans"
    assert body["recent"][0]["human_username"] == "storyteller"
    assert body["recent"][0]["source"] == "ad_tagline"
    # Sparkline: 15 one-minute buckets; the last holds this minute's three calls.
    spark = body["spend_per_min"]
    assert len(spark) == 15
    assert spark[-1] == pytest.approx(0.0047)
    assert sum(spark) == pytest.approx(0.0067)


def test_bot_reaction_records_metered_cost(client, avatar_file, admin_headers):
    _create_bot(client, admin_headers, "meterbot")
    human = _claim_user(client, "postauthor", avatar_file)
    post = client.post("/api/posts", json={"username": "postauthor", "body": "meter this"}).json()

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "meterbot").first()
        jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.post_id == post["id"], models.BotReactionJob.bot_user_id == bot.id)
            .all()
        )
        for job in jobs:
            job.scheduled_for = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
        job_count = len(jobs)
    finally:
        db.close()

    # A response carrying real token usage -> nonzero, attributed cost.
    fake = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="beep boop reaction")],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
    )
    with patch.object(reactions, "_get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = fake
        reactions.run_due_reaction_jobs()

    body = client.get("/api/costs").json()
    # Each job is one metered call at 0.001 + 0.001 = 0.002.
    assert body["total_calls"] == job_count
    assert body["total_cost_usd"] == pytest.approx(0.002 * job_count)
    assert body["by_source"]["bot_reaction"]["calls"] == job_count
    assert body["per_human_user"][0]["username"] == "postauthor"
    assert body["per_human_user"][0]["cost_usd"] == pytest.approx(0.002 * job_count)
    assert human["id"]  # sanity


def test_ad_tagline_records_metered_cost(client, avatar_file, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    _claim_user(client, "adviewer", avatar_file)
    client.post("/api/posts", json={"username": "adviewer", "body": "I am so furious and fed up"})

    from app.ads import targeting

    fake = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Channel that rage.")],
        usage=SimpleNamespace(input_tokens=500, output_tokens=40),
    )
    with patch.object(targeting, "_get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = fake
        client.get("/api/sponsored", params={"username": "adviewer"})

    body = client.get("/api/costs").json()
    assert body["by_source"]["ad_tagline"]["calls"] == 1
    assert body["by_source"]["ad_tagline"]["cost_usd"] == pytest.approx(0.0007)
    assert body["per_human_user"][0]["username"] == "adviewer"
