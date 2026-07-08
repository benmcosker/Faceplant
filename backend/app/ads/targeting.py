"""Emotion targeting: classify a post's mood and serve a matching ad.

`classify_mood` is a transparent keyword classifier (deterministic, offline).
`select_ad` maps a mood to inventory. `build_tagline` optionally has the LLM
write a one-liner that references the user's own words — the "hybrid" copy: a
curated advertiser with a personalized, eerily-apt tagline. Without an
`ANTHROPIC_API_KEY` it falls back to the ad's curated tagline.
"""

import logging
import random
import re

from anthropic import Anthropic
from sqlalchemy.orm import Session

from .. import usage
from ..config import settings
from .inventory import ADS, MOOD_LEXICON, MOODS

logger = logging.getLogger(__name__)

_client: Anthropic | None = None

# Precompute the neutral catch-all once.
_NEUTRAL_ADS = [ad for ad in ADS if "neutral" in ad["moods"]]

# Compile each keyword as a start-of-word match: catches inflections ("rage"
# -> "raging") without false positives from substrings ("average" -> "rage").
_MOOD_PATTERNS: dict[str, list[re.Pattern]] = {
    mood: [re.compile(r"\b" + re.escape(kw)) for kw in kws]
    for mood, kws in MOOD_LEXICON.items()
}


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def classify_mood(text: str) -> str:
    """Maps a post to one mood from MOODS via keyword hits; 'neutral' if none.

    Counts lexicon matches per mood and returns the highest; ties break by the
    priority order in MOODS (grief beats boredom).
    """
    lowered = (text or "").lower()
    best_mood = "neutral"
    best_score = 0
    for mood in MOODS:
        score = sum(1 for pat in _MOOD_PATTERNS.get(mood, []) if pat.search(lowered))
        if score > best_score:
            best_score = score
            best_mood = mood
    return best_mood


def select_ad(mood: str) -> dict:
    """Picks an ad targeting `mood` (random among matches); neutral fallback."""
    matches = [ad for ad in ADS if mood in ad["moods"]]
    if not matches:
        matches = _NEUTRAL_ADS
    return random.choice(matches)


def _build_llm_tagline(ad: dict, post_body: str, mood: str):
    """Has the model write a tagline that nods at the post.

    Returns ``(tagline, api_response)`` — ``(None, None)`` on no key / no post /
    failure. The response carries token usage for the cost meter.
    """
    if not settings.anthropic_api_key or not post_body:
        return None, None
    system = (
        "You are a cynical ad copywriter for a surveillance-capitalism ad network. "
        "Given a user's social media post and the product being advertised, write ONE "
        "short ad tagline (max ~14 words) that subtly references the post so it feels "
        "eerily, invasively targeted at how the user is feeling. Be darkly funny, not "
        "cruel. Output only the tagline: no quotation marks, no hashtags, no emoji."
    )
    user = (
        f"The user seems to be feeling: {mood}.\n"
        f'Their post: "{post_body}"\n'
        f"Product to advertise: {ad['product']} (from {ad['advertiser']})."
    )
    try:
        response = _get_client().messages.create(
            model=settings.default_bot_model,
            max_tokens=48,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        # Strip stray wrapping quotes the model sometimes adds.
        return (text.strip('"').strip() or None), response
    except Exception:
        logger.exception("ad tagline generation failed for %s", ad["advertiser"])
        return None, None


def build_tagline(
    ad: dict,
    post_body: str,
    mood: str,
    *,
    db: Session | None = None,
    human_user_id: int | None = None,
    post_id: int | None = None,
) -> str:
    """The personalized tagline (LLM) or the ad's curated fallback.

    When a `db` session is provided and an LLM call is made, the call's token
    usage is recorded (attributed to `human_user_id`) for the cost meter. The
    caller is responsible for committing.
    """
    tagline, response = _build_llm_tagline(ad, post_body, mood)
    if response is not None and db is not None:
        usage.record(
            db,
            source="ad_tagline",
            model=settings.default_bot_model,
            response=response,
            human_user_id=human_user_id,
            post_id=post_id,
            actor=ad["advertiser"],
        )
    return tagline or ad["tagline"]
