from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.ads import targeting
from app.ads.inventory import ADS, MOODS
from app.config import settings


def _claim_user(client, username, avatar_file):
    return client.post("/api/users", data={"username": username}, files={"avatar": avatar_file}).json()


def _post(client, username, body):
    return client.post("/api/posts", json={"username": username, "body": body}).json()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("my dog died this morning and I can't stop crying", "sad"),
        ("I am so furious, this is absolutely infuriating and unfair", "angry"),
        ("can't sleep, so anxious and overwhelmed about tomorrow", "anxious"),
        ("nobody ever texts me back, I feel so alone", "lonely"),
        ("time to grind and hustle, manifesting my startup empire", "aspirational"),
        ("best day ever, so grateful and excited, yay!", "joyful"),
        ("the weather is average and the report is due friday", "neutral"),
    ],
)
def test_classify_mood(text, expected):
    assert targeting.classify_mood(text) == expected


def test_every_mood_has_inventory():
    covered = {mood for ad in ADS for mood in ad["moods"]}
    for mood in MOODS:
        assert mood in covered, f"no ad targets mood {mood!r}"


def test_select_ad_matches_mood():
    ad = targeting.select_ad("angry")
    assert "angry" in ad["moods"]


def test_build_tagline_falls_back_to_curated_without_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    ad = targeting.select_ad("sad")
    assert targeting.build_tagline(ad, "my cat died", "sad") == ad["tagline"]


def test_build_tagline_uses_llm_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    ad = targeting.select_ad("sad")
    fake = SimpleNamespace(content=[SimpleNamespace(type="text", text="We saw you say goodbye today.")])
    with patch.object(targeting, "_get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = fake
        tagline = targeting.build_tagline(ad, "my dog died this morning", "sad")
    assert tagline == "We saw you say goodbye today."


def test_posting_profiles_the_users_mood(client, avatar_file, monkeypatch):
    # No key: the sponsored endpoint uses the curated tagline (deterministic).
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    _claim_user(client, "griever", avatar_file)
    _post(client, "griever", "I miss her so much, my heart is broken")

    res = client.get("/api/sponsored", params={"username": "griever"})
    assert res.status_code == 200
    ad = res.json()
    # Targeted at the profiled mood, not generic.
    assert ad["mood"] == "sad"
    assert ad["advertiser"] != "Generic Brand™"
    assert ad["tagline"] and ad["cta"] and ad["body"]


def test_unprofiled_user_gets_the_neutral_ad(client, avatar_file, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    # Claim a user but never post -> no mood profiled yet.
    _claim_user(client, "blankslate", avatar_file)

    res = client.get("/api/sponsored", params={"username": "blankslate"})
    assert res.status_code == 200
    ad = res.json()
    assert ad["mood"] == "neutral"
    assert ad["advertiser"] == "Generic Brand™"


def test_sponsored_unknown_user_404(client):
    res = client.get("/api/sponsored", params={"username": "ghost"})
    assert res.status_code == 404


def test_sponsored_tagline_personalized_with_key(client, avatar_file, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    _claim_user(client, "angryuser", avatar_file)
    _post(client, "angryuser", "I am so furious, this is infuriating and unfair")

    fake = SimpleNamespace(content=[SimpleNamespace(type="text", text="Still fuming? Caffeinate the rage.")])
    with patch.object(targeting, "_get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = fake
        res = client.get("/api/sponsored", params={"username": "angryuser"})

    ad = res.json()
    assert ad["mood"] == "angry"
    assert ad["tagline"] == "Still fuming? Caffeinate the rage."
    # The model was handed the user's actual words.
    user_prompt = mock_client.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "infuriating" in user_prompt
