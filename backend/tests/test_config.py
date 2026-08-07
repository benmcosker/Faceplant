import pytest
from pydantic import ValidationError

from app.config import Settings


def test_reaction_poll_seconds_default():
    assert Settings().reaction_poll_seconds == 20


def test_reaction_poll_seconds_override(monkeypatch):
    monkeypatch.setenv("REACTION_POLL_SECONDS", "3")
    assert Settings().reaction_poll_seconds == 3


def test_reaction_poll_seconds_rejects_zero(monkeypatch):
    monkeypatch.setenv("REACTION_POLL_SECONDS", "0")
    with pytest.raises(ValidationError):
        Settings()
