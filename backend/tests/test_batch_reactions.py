"""Tests for the Message Batches path of the bot-reaction engine.

When settings.use_batch_api is on, reactions are submitted as one async batch
(jobs go pending -> submitted) and their comments/likes/cost are written only
once the batch ends and reconcile_reaction_batches picks up the results. These
tests drive both phases with a mocked Anthropic client.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app import models
from app.bots import reactions
from app.config import settings
from app.db import SessionLocal


def _create_bot(client, admin_headers, username, persona="an obvious bot"):
    return client.post(
        "/api/admin/bots",
        json={
            "username": username,
            "password": "password123",
            "persona": persona,
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
        return [job.id for job in jobs]
    finally:
        db.close()


def _succeeded_result(custom_id, text):
    """A stand-in for one entry of client.beta.messages.batches.results()."""
    return SimpleNamespace(
        custom_id=custom_id,
        result=SimpleNamespace(
            type="succeeded",
            message=SimpleNamespace(
                content=[SimpleNamespace(type="text", text=text)],
                usage=SimpleNamespace(input_tokens=12, output_tokens=7),
            ),
        ),
    )


def test_batch_submit_marks_jobs_submitted_and_records_batch(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_batch_api", True)
    _create_bot(client, admin_headers, "batchbot")
    login("batchhuman@example.com", "batchhuman")
    post = client.post("/api/posts", json={"body": "batch me up"}).json()
    _make_jobs_due(post["id"], "batchbot")

    with patch.object(reactions, "_get_client") as mock_get_client:
        batches = mock_get_client.return_value.beta.messages.batches
        batches.create.return_value = SimpleNamespace(id="msgbatch_abc")
        reactions.run_due_reaction_jobs()  # submit phase

    # The batch carried one request per due job, correctly shaped.
    requests = batches.create.call_args.kwargs["requests"]
    assert len(requests) >= 1
    for req in requests:
        assert req["custom_id"].isdigit()
        assert req["params"]["max_tokens"] == 160
        assert "an obvious bot" in req["params"]["system"]
        assert "batch me up" in req["params"]["messages"][0]["content"]

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "batchbot").first()
        jobs = (
            db.query(models.BotReactionJob)
            .filter(models.BotReactionJob.post_id == post["id"], models.BotReactionJob.bot_user_id == bot.id)
            .all()
        )
        assert jobs and all(j.status == "submitted" and j.batch_id == "msgbatch_abc" for j in jobs)
        # No comment/like/cost is written at submit time — only after the batch ends.
        assert db.query(models.Comment).filter(models.Comment.post_id == post["id"]).count() == 0
        assert db.query(models.TokenUsage).count() == 0

        rb = db.query(models.ReactionBatch).filter(
            models.ReactionBatch.anthropic_batch_id == "msgbatch_abc"
        ).first()
        assert rb is not None
        assert rb.status == "submitted"
        assert rb.submitted_count == len(jobs)
    finally:
        db.close()


def test_batch_reconcile_writes_comments_likes_and_cost(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_batch_api", True)
    _create_bot(client, admin_headers, "batchbot2")
    login("batchhuman2@example.com", "batchhuman2")
    post = client.post("/api/posts", json={"body": "reconcile this"}).json()
    _make_jobs_due(post["id"], "batchbot2")

    with patch.object(reactions, "_get_client") as mock_get_client:
        batches = mock_get_client.return_value.beta.messages.batches
        batches.create.return_value = SimpleNamespace(id="msgbatch_rec")
        reactions.run_due_reaction_jobs()  # submit

        db = SessionLocal()
        try:
            bot = db.query(models.User).filter(models.User.username == "batchbot2").first()
            job_ids = [
                j.id
                for j in db.query(models.BotReactionJob).filter(
                    models.BotReactionJob.batch_id == "msgbatch_rec"
                )
            ]
        finally:
            db.close()

        # The batch has finished; results arrive keyed by custom_id (any order).
        batches.retrieve.return_value = SimpleNamespace(processing_status="ended")
        batches.results.return_value = [
            _succeeded_result(str(jid), "beep boop batched reaction") for jid in reversed(job_ids)
        ]
        reactions.reconcile_reaction_batches()

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "batchbot2").first()
        jobs = db.query(models.BotReactionJob).filter(
            models.BotReactionJob.batch_id == "msgbatch_rec"
        ).all()
        assert jobs and all(j.status == "done" and j.executed_at is not None for j in jobs)

        comments = db.query(models.Comment).filter(
            models.Comment.post_id == post["id"], models.Comment.user_id == bot.id
        ).all()
        assert len(comments) == len(job_ids)
        assert all(c.body == "beep boop batched reaction" for c in comments)

        # The bot liked the post once, regardless of how many reactions it left.
        likes = db.query(models.Like).filter(
            models.Like.post_id == post["id"], models.Like.user_id == bot.id
        ).all()
        assert len(likes) == 1

        # Cost was metered per reaction, attributed to the human whose post it was.
        usage_rows = db.query(models.TokenUsage).filter(
            models.TokenUsage.source == "bot_reaction"
        ).all()
        assert len(usage_rows) == len(job_ids)
        human = db.query(models.User).filter(models.User.username == "batchhuman2").first()
        assert all(u.human_user_id == human.id for u in usage_rows)

        rb = db.query(models.ReactionBatch).filter(
            models.ReactionBatch.anthropic_batch_id == "msgbatch_rec"
        ).first()
        assert rb.status == "ended"
    finally:
        db.close()


def test_batch_reconcile_marks_errored_results_failed(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_batch_api", True)
    _create_bot(client, admin_headers, "batchbot3")
    login("batchhuman3@example.com", "batchhuman3")
    post = client.post("/api/posts", json={"body": "this one errors"}).json()
    _make_jobs_due(post["id"], "batchbot3")

    with patch.object(reactions, "_get_client") as mock_get_client:
        batches = mock_get_client.return_value.beta.messages.batches
        batches.create.return_value = SimpleNamespace(id="msgbatch_err")
        reactions.run_due_reaction_jobs()

        db = SessionLocal()
        try:
            job_ids = [
                j.id
                for j in db.query(models.BotReactionJob).filter(
                    models.BotReactionJob.batch_id == "msgbatch_err"
                )
            ]
        finally:
            db.close()

        batches.retrieve.return_value = SimpleNamespace(processing_status="ended")
        batches.results.return_value = [
            SimpleNamespace(
                custom_id=str(jid),
                result=SimpleNamespace(type="errored", error=SimpleNamespace(type="api_error")),
            )
            for jid in job_ids
        ]
        reactions.reconcile_reaction_batches()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(
            models.BotReactionJob.batch_id == "msgbatch_err"
        ).all()
        assert jobs and all(j.status == "failed" for j in jobs)
        assert db.query(models.Comment).filter(models.Comment.post_id == post["id"]).count() == 0
        assert db.query(models.TokenUsage).count() == 0
    finally:
        db.close()


def test_batch_submit_skips_when_spend_ceiling_reached(client, login, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "use_batch_api", True)
    monkeypatch.setattr(settings, "global_spend_ceiling_usd", 1.0)
    _create_bot(client, admin_headers, "batchbot4")
    login("batchhuman4@example.com", "batchhuman4")
    post = client.post("/api/posts", json={"body": "too pricey"}).json()
    _make_jobs_due(post["id"], "batchbot4")

    db = SessionLocal()
    try:
        db.add(models.TokenUsage(source="bot_reaction", model="claude-haiku-4-5", cost_usd=1.0))
        db.commit()
    finally:
        db.close()

    with patch.object(reactions, "_get_client") as mock_get_client:
        batches = mock_get_client.return_value.beta.messages.batches
        reactions.run_due_reaction_jobs()
        # No batch is opened once the meter has crossed the ceiling.
        batches.create.assert_not_called()

    db = SessionLocal()
    try:
        jobs = db.query(models.BotReactionJob).filter(
            models.BotReactionJob.post_id == post["id"]
        ).all()
        assert jobs and all(j.status == "skipped" for j in jobs)
        assert db.query(models.ReactionBatch).count() == 0
    finally:
        db.close()
