def test_like_unknown_post_404(client, login):
    login("liker@example.com", "liker")
    response = client.post("/api/posts/999/like")
    assert response.status_code == 404


def test_like_without_session_401(client, login):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()
    client.cookies.clear()

    response = client.post(f"/api/posts/{post['id']}/like")
    assert response.status_code == 401


def test_like_toggle_on_and_off(client, login):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()

    login("liker@example.com", "liker")
    liked = client.post(f"/api/posts/{post['id']}/like")
    assert liked.status_code == 200
    assert liked.json() == {"liked": True, "count": 1}

    unliked = client.post(f"/api/posts/{post['id']}/like")
    assert unliked.status_code == 200
    assert unliked.json() == {"liked": False, "count": 0}

    feed_post = client.get("/api/posts").json()[0]
    assert feed_post["like_count"] == 0
