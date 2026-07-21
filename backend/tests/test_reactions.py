from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import giphy, models
from app.bots import reactions
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


def test_human_post_enqueues_jobs_in_both_windows(client, login, admin_headers):
    bot_usernames = [f"bot{i}" for i in range(10)]
    for name in bot_usernames:
        _create_bot(client, admin_headers, name)
    login("human@example.com", "human")

    post = client.post("/api/posts", json={"body": "hello"}).json()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        assert settings.short_wave_size_min + settings.long_wave_size_min <= len(jobs)
        assert len(jobs) <= settings.short_wave_size_max + settings.long_wave_size_max

        post_row = db.get(models.Post, post["id"])
        short_cutoff = post_row.created_at + timedelta(minutes=settings.short_reaction_window_minutes)
        long_lower = post_row.created_at + timedelta(minutes=settings.long_reaction_window_min_minutes)
        long_upper = post_row.created_at + timedelta(minutes=settings.long_reaction_window_max_minutes)

        short_jobs = [j for j in jobs if j.scheduled_for <= short_cutoff]
        long_jobs = [j for j in jobs if j.scheduled_for > short_cutoff]

        assert len(short_jobs) > 0
        assert len(long_jobs) > 0
        for job in long_jobs:
            assert long_lower <= job.scheduled_for <= long_upper
        for job in jobs:
            assert job.status == "pending"
    finally:
        db.close()


def test_no_bots_enqueues_nothing(client, login):
    login("lonelyhuman@example.com", "lonelyhuman")
    post = client.post("/api/posts", json={"body": "anyone here?"}).json()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        assert jobs == []
    finally:
        db.close()


def test_run_due_reaction_jobs_creates_comment_and_like_and_marks_done(client, login, admin_headers):
    _create_bot(client, admin_headers, "reactorbot")
    login("human2@example.com", "human2")
    post = client.post("/api/posts", json={"body": "react to this"}).json()

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "reactorbot").first()
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

    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="lol nice post, totally human reaction here")]
    )
    with patch.object(reactions, "_get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = fake_response
        reactions.run_due_reaction_jobs()

    create_kwargs = mock_get_client.return_value.messages.create.call_args.kwargs
    assert create_kwargs["max_tokens"] == 160
    assert "system" in create_kwargs
    assert "an obvious bot" in create_kwargs["system"]
    assert create_kwargs["messages"][0]["role"] == "user"
    assert "react to this" in create_kwargs["messages"][0]["content"]

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "reactorbot").first()
        refreshed_jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.post_id == post["id"], models.BotReactionJob.bot_user_id == bot.id)
            .all()
        )
        assert len(refreshed_jobs) == job_count
        for job in refreshed_jobs:
            assert job.status == "done"
            assert job.executed_at is not None

        comments = db.query(models.Comment).filter(
            models.Comment.post_id == post["id"], models.Comment.user_id == bot.id
        ).all()
        assert len(comments) == job_count
        assert all(c.body == "lol nice post, totally human reaction here" for c in comments)

        likes = db.query(models.Like).filter(
            models.Like.post_id == post["id"], models.Like.user_id == bot.id
        ).all()
        assert len(likes) == 1
    finally:
        db.close()


def test_run_due_reaction_jobs_includes_thread_context_when_comments_exist(client, login, admin_headers):
    _create_bot(client, admin_headers, "threadbot")
    login("human4@example.com", "human4")
    post = client.post("/api/posts", json={"body": "thread context test"}).json()

    login("commenter4@example.com", "commenter4")
    client.post(
        f"/api/posts/{post['id']}/comments",
        json={"body": "first reply in the thread"},
    )

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "threadbot").first()
        jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.post_id == post["id"], models.BotReactionJob.bot_user_id == bot.id)
            .all()
        )
        for job in jobs:
            job.scheduled_for = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="joining the thread now")]
    )
    with patch.object(reactions, "_get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = fake_response
        reactions.run_due_reaction_jobs()

    user_prompt = mock_get_client.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "commenter4" in user_prompt
    assert "first reply in the thread" in user_prompt


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
    finally:
        db.close()


def _bot_comment_bodies(post_id, bot_username):
    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == bot_username).first()
        comments = (
            db.query(models.Comment)
            .filter(models.Comment.post_id == post_id, models.Comment.user_id == bot.id)
            .all()
        )
        return [c.body for c in comments]
    finally:
        db.close()


def _giphy_response(url):
    """A stand-in for httpx.get()'s return value from Giphy's /random endpoint."""
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"data": {"images": {"original": {"url": url}}}},
    )


def test_giphy_bot_posts_gif_url_not_prose(client, login, admin_headers, monkeypatch):
    # gifgremlin is a uses_giphy=True persona in the roster, so reactions.py
    # should branch into the caption + Giphy path for it.
    _create_bot(client, admin_headers, "gifgremlin")
    login("gifhuman@example.com", "gifhuman")
    post = client.post("/api/posts", json={"body": "big news today"}).json()
    _make_jobs_due(post["id"], "gifgremlin")

    monkeypatch.setattr(settings, "giphy_api_key", "test-giphy-key")
    gif_url = "https://media3.giphy.com/media/abc123/giphy.gif"
    fake_model_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"caption": "mood", "tag": "mic drop"}')]
    )

    with patch.object(reactions, "_get_client") as mock_get_client, patch.object(
        giphy.httpx, "get", return_value=_giphy_response(gif_url)
    ) as mock_httpx_get:
        mock_get_client.return_value.messages.create.return_value = fake_model_response
        reactions.run_due_reaction_jobs()

    # Giphy was queried with the model-chosen tag and the configured key.
    giphy_kwargs = mock_httpx_get.call_args.kwargs
    assert mock_httpx_get.call_args.args[0] == giphy.GIPHY_RANDOM_URL
    assert giphy_kwargs["params"]["tag"] == "mic drop"
    assert giphy_kwargs["params"]["api_key"] == "test-giphy-key"

    bodies = _bot_comment_bodies(post["id"], "gifgremlin")
    assert bodies, "expected the gif bot to leave a comment"
    for body in bodies:
        # The comment body carries the GIF URL (as its own trailing line), not prose.
        lines = body.split("\n")
        assert lines[-1] == gif_url
        assert lines[-1].startswith("http")
        assert reactions._parse_caption_and_tag  # sanity: helper is exported


def test_giphy_bot_falls_back_to_caption_without_api_key(client, login, admin_headers, monkeypatch):
    _create_bot(client, admin_headers, "gifgremlin")
    login("gifhuman2@example.com", "gifhuman2")
    post = client.post("/api/posts", json={"body": "no key here"}).json()
    _make_jobs_due(post["id"], "gifgremlin")

    monkeypatch.setattr(settings, "giphy_api_key", "")
    fake_model_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"caption": "welp", "tag": "shrug"}')]
    )

    with patch.object(reactions, "_get_client") as mock_get_client, patch.object(
        giphy.httpx, "get"
    ) as mock_httpx_get:
        mock_get_client.return_value.messages.create.return_value = fake_model_response
        reactions.run_due_reaction_jobs()

    # Without a key, Giphy is never called and we fall back to the caption alone.
    mock_httpx_get.assert_not_called()
    bodies = _bot_comment_bodies(post["id"], "gifgremlin")
    assert bodies and all(body == "welp" for body in bodies)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"caption": "mood", "tag": "eye roll"}', ("mood", "eye roll")),
        ('```json\n{"caption": "welp", "tag": "shrug"}\n```', ("welp", "shrug")),
        ("Sure! {\"caption\": \"lol\", \"tag\": \"popcorn\"}", ("lol", "popcorn")),
        ("not json at all", ("", "")),
    ],
)
def test_parse_caption_and_tag(raw, expected):
    assert reactions._parse_caption_and_tag(raw) == expected


def test_run_due_reaction_jobs_marks_failed_on_error(client, login, admin_headers):
    _create_bot(client, admin_headers, "brokenbot")
    login("human3@example.com", "human3")
    post = client.post("/api/posts", json={"body": "will fail"}).json()

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "brokenbot").first()
        jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.post_id == post["id"], models.BotReactionJob.bot_user_id == bot.id)
            .all()
        )
        for job in jobs:
            job.scheduled_for = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    with patch.object(reactions, "_get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.side_effect = RuntimeError("api error")
        reactions.run_due_reaction_jobs()

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "brokenbot").first()
        refreshed_jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.post_id == post["id"], models.BotReactionJob.bot_user_id == bot.id)
            .all()
        )
        for job in refreshed_jobs:
            assert job.status == "failed"
            assert job.executed_at is not None
    finally:
        db.close()
