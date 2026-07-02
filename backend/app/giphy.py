"""Thin Giphy client shared by the GIF-first bots and the `/giphy` comment command.

Both entry points return a plain GIF URL string (or "" when Giphy is
unavailable — no API key, no match, or a request error). Callers decide what
to do with an empty result: bots fall back to a caption-only reply, the
`/giphy` command falls back to the literal text the user typed.
"""

import logging
import random

import httpx

from .config import settings

logger = logging.getLogger(__name__)

GIPHY_RANDOM_URL = "https://api.giphy.com/v1/gifs/random"
GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"

# How many search hits to pull before picking one at random, so repeated
# `/giphy cats` don't all return the identical top result.
SEARCH_POOL_SIZE = 15


def _image_url(item: dict) -> str:
    """Pulls the canonical GIF URL out of a Giphy image object."""
    original = (item.get("images") or {}).get("original") or {}
    return (original.get("url") or item.get("image_url") or "").strip()


def fetch_random_gif_url(tag: str) -> str:
    """A random GIF for `tag` (used by GIF-first bots for variety)."""
    if not settings.giphy_api_key or not tag:
        return ""
    response = httpx.get(
        GIPHY_RANDOM_URL,
        params={"api_key": settings.giphy_api_key, "tag": tag, "rating": "pg-13"},
        timeout=10,
    )
    response.raise_for_status()
    return _image_url(response.json().get("data") or {})


def search_gif_url(keyword: str) -> str:
    """A GIF matching `keyword` (used by the `/giphy <keyword>` comment command).

    Searches the top results and returns one at random for a Slack-like feel,
    so the same keyword doesn't always resolve to the exact same GIF.
    """
    if not settings.giphy_api_key or not keyword:
        return ""
    response = httpx.get(
        GIPHY_SEARCH_URL,
        params={
            "api_key": settings.giphy_api_key,
            "q": keyword,
            "limit": SEARCH_POOL_SIZE,
            "rating": "pg-13",
        },
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("data") or []
    if not results:
        return ""
    return _image_url(random.choice(results))
