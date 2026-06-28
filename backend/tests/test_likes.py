def _claim_user(client, username, avatar_file):
    return client.post("/api/users", data={"username": username}, files={"avatar": avatar_file}).json()


def _create_post(client, username, body="hello world"):
    return client.post("/api/posts", json={"username": username, "body": body}).json()


def test_like_unknown_post_404(client):
    response = client.post("/api/posts/999/like", json={"username": "x"})
    assert response.status_code == 404


def test_like_unknown_user_404(client, avatar_file):
    _claim_user(client, "author", avatar_file)
    post = _create_post(client, "author")

    response = client.post(f"/api/posts/{post['id']}/like", json={"username": "ghost"})
    assert response.status_code == 404


def test_like_toggle_on_and_off(client, avatar_file):
    _claim_user(client, "author", avatar_file)
    _claim_user(client, "liker", avatar_file)
    post = _create_post(client, "author")

    liked = client.post(f"/api/posts/{post['id']}/like", json={"username": "liker"})
    assert liked.status_code == 200
    assert liked.json() == {"liked": True, "count": 1}

    unliked = client.post(f"/api/posts/{post['id']}/like", json={"username": "liker"})
    assert unliked.status_code == 200
    assert unliked.json() == {"liked": False, "count": 0}

    feed_post = client.get("/api/posts").json()[0]
    assert feed_post["like_count"] == 0
