from types import SimpleNamespace
from unittest.mock import patch

from app import giphy
from app.config import settings


def _giphy_search_response(url):
    """Stand-in for httpx.get()'s return value from Giphy's /search endpoint."""
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"data": [{"images": {"original": {"url": url}}}]},
    )


def test_comments_on_unknown_post_404(client, login):
    response = client.get("/api/posts/999/comments")
    assert response.status_code == 404

    login("author@example.com", "author")
    response = client.post("/api/posts/999/comments", json={"body": "y"})
    assert response.status_code == 404


def test_add_comment_without_session_401(client, login):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()
    client.cookies.clear()

    response = client.post(f"/api/posts/{post['id']}/comments", json={"body": "hi"})
    assert response.status_code == 401


def test_add_and_list_comments(client, login):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()

    login("commenter@example.com", "commenter")
    response = client.post(f"/api/posts/{post['id']}/comments", json={"body": "nice post"})
    assert response.status_code == 200
    comment = response.json()
    assert comment["body"] == "nice post"
    assert comment["author"]["username"] == "commenter"

    listing = client.get(f"/api/posts/{post['id']}/comments")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    feed_post = client.get("/api/posts").json()[0]
    assert feed_post["comment_count"] == 1


def test_giphy_command_stores_gif_url(client, login, monkeypatch):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()
    login("gifposter@example.com", "gifposter")

    monkeypatch.setattr(settings, "giphy_api_key", "test-giphy-key")
    gif_url = "https://media3.giphy.com/media/xyz/giphy.gif"

    with patch.object(giphy.httpx, "get", return_value=_giphy_search_response(gif_url)) as mock_get:
        response = client.post(
            f"/api/posts/{post['id']}/comments",
            json={"body": "/giphy this is fine"},
        )

    assert response.status_code == 200
    # The stored comment body is the GIF URL, not the literal command text.
    assert response.json()["body"] == gif_url
    # Giphy was searched with the keyword from the command (case preserved).
    call = mock_get.call_args
    assert call.args[0] == giphy.GIPHY_SEARCH_URL
    assert call.kwargs["params"]["q"] == "this is fine"
    assert call.kwargs["params"]["api_key"] == "test-giphy-key"


def test_giphy_command_is_case_insensitive(client, login, monkeypatch):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()
    login("gifposter@example.com", "gifposter")

    monkeypatch.setattr(settings, "giphy_api_key", "test-giphy-key")
    gif_url = "https://media0.giphy.com/media/abc/giphy.gif"

    with patch.object(giphy.httpx, "get", return_value=_giphy_search_response(gif_url)) as mock_get:
        response = client.post(
            f"/api/posts/{post['id']}/comments",
            json={"body": "/GIPHY   dancing cat  "},
        )

    assert response.json()["body"] == gif_url
    assert mock_get.call_args.kwargs["params"]["q"] == "dancing cat"


def test_giphy_command_falls_back_to_text_without_key(client, login, monkeypatch):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()
    login("gifposter@example.com", "gifposter")

    monkeypatch.setattr(settings, "giphy_api_key", "")

    with patch.object(giphy.httpx, "get") as mock_get:
        response = client.post(
            f"/api/posts/{post['id']}/comments",
            json={"body": "/giphy nope"},
        )

    # No key: Giphy is never called and the literal command text is kept.
    mock_get.assert_not_called()
    assert response.json()["body"] == "/giphy nope"


def test_giphy_command_falls_back_to_text_when_no_results(client, login, monkeypatch):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()
    login("gifposter@example.com", "gifposter")

    monkeypatch.setattr(settings, "giphy_api_key", "test-giphy-key")
    empty = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"data": []})

    with patch.object(giphy.httpx, "get", return_value=empty):
        response = client.post(
            f"/api/posts/{post['id']}/comments",
            json={"body": "/giphy asdfqwerzxcv"},
        )

    assert response.json()["body"] == "/giphy asdfqwerzxcv"


def test_plain_comment_never_calls_giphy(client, login):
    login("author@example.com", "author")
    post = client.post("/api/posts", json={"body": "hello world"}).json()
    login("commenter@example.com", "commenter")

    with patch.object(giphy.httpx, "get") as mock_get:
        response = client.post(
            f"/api/posts/{post['id']}/comments",
            json={"body": "just a normal /giphy-less comment"},
        )

    mock_get.assert_not_called()
    assert response.json()["body"] == "just a normal /giphy-less comment"
