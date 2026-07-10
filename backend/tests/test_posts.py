def _claim_user(client, username, avatar_file):
    response = client.post("/api/users", data={"username": username}, files={"avatar": avatar_file})
    assert response.status_code == 200
    return response.json()


def test_create_post_unknown_user_404(client):
    response = client.post("/api/posts", json={"username": "ghost", "body": "hello"})
    assert response.status_code == 404


def test_first_and_second_post_by_same_user(client, avatar_file):
    _claim_user(client, "poster", avatar_file)

    first = client.post("/api/posts", json={"username": "poster", "body": "first post"})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["body"] == "first post"
    assert first_body["author"]["username"] == "poster"
    assert first_body["like_count"] == 0
    assert first_body["comment_count"] == 0

    second = client.post("/api/posts", json={"username": "poster", "body": "second post"})
    assert second.status_code == 200

    feed = client.get("/api/posts")
    assert feed.status_code == 200
    bodies = [p["body"] for p in feed.json()]
    assert bodies[0] == "second post"
    assert bodies[1] == "first post"


def test_post_includes_top_comments_peek(client, avatar_file):
    _claim_user(client, "peeker", avatar_file)
    post = client.post("/api/posts", json={"username": "peeker", "body": "topic"}).json()
    for i in range(3):
        client.post(f"/api/posts/{post['id']}/comments", json={"username": "peeker", "body": f"reply {i}"})

    feed_post = client.get("/api/posts").json()[0]
    # Only the first two replies are inlined, in thread (oldest-first) order.
    assert feed_post["comment_count"] == 3
    bodies = [c["body"] for c in feed_post["top_comments"]]
    assert bodies == ["reply 0", "reply 1"]


def test_post_top_comments_empty_when_no_replies(client, avatar_file):
    _claim_user(client, "quiet", avatar_file)
    client.post("/api/posts", json={"username": "quiet", "body": "no replies yet"})

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


def test_thread_human_share_craters_under_a_bot_pileon(client, avatar_file, admin_headers):
    _claim_user(client, "lonelyhuman", avatar_file)
    post = client.post("/api/posts", json={"username": "lonelyhuman", "body": "hi"}).json()
    _create_bot(client, admin_headers, "swarmbot")
    for i in range(3):
        client.post(f"/api/posts/{post['id']}/comments", json={"username": "swarmbot", "body": f"beep {i}"})

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
    }


def test_thread_human_share_is_full_for_a_bare_post(client, avatar_file):
    _claim_user(client, "solo", avatar_file)
    client.post("/api/posts", json={"username": "solo", "body": "no replies yet"})

    feed_post = client.get("/api/posts").json()[0]
    assert feed_post["human_share"] == 1.0
    assert feed_post["total_messages"] == 1
    assert feed_post["bot_messages"] == 0


def test_thread_stats_unknown_post_404(client):
    assert client.get("/api/posts/999/thread-stats").status_code == 404


def test_feed_pagination_cursor(client, avatar_file):
    _claim_user(client, "pager", avatar_file)
    for i in range(3):
        client.post("/api/posts", json={"username": "pager", "body": f"post {i}"})

    first_page = client.get("/api/posts", params={"limit": 2}).json()
    assert len(first_page) == 2

    cursor = first_page[-1]["id"]
    second_page = client.get("/api/posts", params={"limit": 2, "cursor": cursor}).json()
    assert len(second_page) == 1
    assert second_page[0]["id"] < cursor
