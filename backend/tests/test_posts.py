from app import models
from app.db import SessionLocal


def test_create_post_requires_login(client):
    response = client.post("/api/posts", json={"body": "hello"})
    assert response.status_code == 401


def test_first_and_second_post_by_same_user(client, login):
    login("poster@example.com", "poster")

    first = client.post("/api/posts", json={"body": "first post"})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["body"] == "first post"
    assert first_body["author"]["username"] == "poster"
    assert first_body["like_count"] == 0
    assert first_body["comment_count"] == 0

    second = client.post("/api/posts", json={"body": "second post"})
    assert second.status_code == 200

    feed = client.get("/api/posts")
    assert feed.status_code == 200
    bodies = [p["body"] for p in feed.json()]
    assert bodies[0] == "second post"
    assert bodies[1] == "first post"


def test_post_includes_top_comments_peek(client, login):
    login("peeker@example.com", "peeker")
    post = client.post("/api/posts", json={"body": "topic"}).json()
    for i in range(3):
        client.post(f"/api/posts/{post['id']}/comments", json={"body": f"reply {i}"})

    feed_post = client.get("/api/posts").json()[0]
    # Only the first two replies are inlined, in thread (oldest-first) order.
    assert feed_post["comment_count"] == 3
    bodies = [c["body"] for c in feed_post["top_comments"]]
    assert bodies == ["reply 0", "reply 1"]


def test_post_top_comments_empty_when_no_replies(client, login):
    login("quiet@example.com", "quiet")
    client.post("/api/posts", json={"body": "no replies yet"})

    feed_post = client.get("/api/posts").json()[0]
    assert feed_post["comment_count"] == 0
    assert feed_post["top_comments"] == []


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
    )


def test_thread_human_share_craters_under_a_bot_pileon(client, login, admin_headers):
    login("lonelyhuman@example.com", "lonelyhuman")
    post = client.post("/api/posts", json={"body": "hi"}).json()
    _create_bot(client, admin_headers, "swarmbot")

    db = SessionLocal()
    try:
        bot = db.query(models.User).filter(models.User.username == "swarmbot").first()
        for i in range(3):
            db.add(models.Comment(post_id=post["id"], user_id=bot.id, body=f"beep {i}"))
        db.commit()
    finally:
        db.close()

    feed_post = client.get("/api/posts").json()[0]
    # 1 human message (the post) out of 4 total (post + 3 bot comments) = 25% human.
    assert feed_post["total_messages"] == 4
    assert feed_post["human_messages"] == 1
    assert feed_post["bot_messages"] == 3
    assert feed_post["human_share"] == 0.25

    # The dedicated live endpoint agrees.
    stats = client.get(f"/api/posts/{post['id']}/thread-stats").json()
    assert stats == {
        "human_share": 0.25,
        "human_messages": 1,
        "bot_messages": 3,
        "total_messages": 4,
        "like_count": 0,
    }


def test_thread_human_share_is_full_for_a_bare_post(client, login):
    login("solo@example.com", "solo")
    client.post("/api/posts", json={"body": "no replies yet"})

    feed_post = client.get("/api/posts").json()[0]
    assert feed_post["human_share"] == 1.0
    assert feed_post["total_messages"] == 1
    assert feed_post["bot_messages"] == 0


def test_thread_stats_unknown_post_404(client):
    assert client.get("/api/posts/999/thread-stats").status_code == 404


def test_feed_pagination_cursor(client, login):
    login("pager@example.com", "pager")
    for i in range(3):
        client.post("/api/posts", json={"body": f"post {i}"})

    first_page = client.get("/api/posts", params={"limit": 2}).json()
    assert len(first_page) == 2

    cursor = first_page[-1]["id"]
    second_page = client.get("/api/posts", params={"limit": 2, "cursor": cursor}).json()
    assert len(second_page) == 1
    assert second_page[0]["id"] < cursor
