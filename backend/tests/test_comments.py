def _claim_user(client, username, avatar_file):
    return client.post("/api/users", data={"username": username}, files={"avatar": avatar_file}).json()


def _create_post(client, username, body="hello world"):
    return client.post("/api/posts", json={"username": username, "body": body}).json()


def test_comments_on_unknown_post_404(client):
    response = client.get("/api/posts/999/comments")
    assert response.status_code == 404

    response = client.post("/api/posts/999/comments", json={"username": "x", "body": "y"})
    assert response.status_code == 404


def test_add_comment_unknown_user_404(client, avatar_file):
    _claim_user(client, "author", avatar_file)
    post = _create_post(client, "author")

    response = client.post(
        f"/api/posts/{post['id']}/comments", json={"username": "ghost", "body": "hi"}
    )
    assert response.status_code == 404


def test_add_and_list_comments(client, avatar_file):
    _claim_user(client, "author", avatar_file)
    _claim_user(client, "commenter", avatar_file)
    post = _create_post(client, "author")

    response = client.post(
        f"/api/posts/{post['id']}/comments", json={"username": "commenter", "body": "nice post"}
    )
    assert response.status_code == 200
    comment = response.json()
    assert comment["body"] == "nice post"
    assert comment["author"]["username"] == "commenter"

    listing = client.get(f"/api/posts/{post['id']}/comments")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    feed_post = client.get("/api/posts").json()[0]
    assert feed_post["comment_count"] == 1
