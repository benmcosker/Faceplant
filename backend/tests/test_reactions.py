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


def test_human_post_enqueues_jobs_in_both_windows(client, avatar_file, admin_headers):
    bot_usernames = [f"bot{i}" for i in range(10)]
    for name in bot_usernames:
        _create_bot(client, admin_headers, name)
    _claim_user(client, "human", avatar_file)

    post = client.post("/api/posts", json={"username": "human", "body": "hello"}).json()

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


def test_bot_post_enqueues_no_jobs(client, avatar_file, admin_headers):
    _create_bot(client, admin_headers, "soloBot")

    post = client.post("/api/posts", json={"username": "solobot", "body": "I am a bot"}).json()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        assert jobs == []
    finally:
        db.close()


def test_no_bots_enqueues_nothing(client, avatar_file):
    _claim_user(client, "lonelyhuman", avatar_file)
    post = client.post("/api/posts", json={"username": "lonelyhuman", "body": "anyone here?"}).json()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(models.BotReactionJob.post_id == post["id"]).all()
        assert jobs == []
    finally:
        db.close()


def test_run_due_reaction_jobs_creates_comment_and_like_and_marks_done(client, avatar_file, admin_headers):
    _create_bot(client, admin_headers, "reactorbot")
    _claim_user(client, "human2", avatar_file)
    post = client.post("/api/posts", json={"username": "human2", "body": "react to this"}).json()

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


def test_run_due_reaction_jobs_marks_failed_on_error(client, avatar_file, admin_headers):
    _create_bot(client, admin_headers, "brokenbot")
    _claim_user(client, "human3", avatar_file)
    post = client.post("/api/posts", json={"username": "human3", "body": "will fail"}).json()

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
