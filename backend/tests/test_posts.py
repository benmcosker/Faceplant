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
