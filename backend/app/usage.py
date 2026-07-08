"""Token-cost accounting for the Claude API calls that power the app.

Every bot reaction and every emotion-targeted ad tagline is a real Anthropic
call that spends tokens and therefore money. This module turns each response's
`usage` into a dollar estimate and records it, so "The Meter" can show the
running cost of manufactured engagement — attributed back to the human whose
post triggered it.
"""

import logging

from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)

# (input $/MTok, output $/MTok). Verified against the Claude API pricing
# reference. Update here if the model or its pricing changes; historical rows
# keep the cost computed at record time, so past totals don't shift.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
}
_DEFAULT_PRICING = (1.00, 5.00)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimated USD for a single call, from the per-model token prices."""
    in_price, out_price = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return input_tokens / 1_000_000 * in_price + output_tokens / 1_000_000 * out_price


def _tokens(response) -> tuple[int, int]:
    """Pulls (input, output) tokens off a response's usage; (0, 0) if absent.

    Defensive on purpose — a mocked or malformed response must never break the
    reaction/ad that produced it just because metering couldn't read usage.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)


def record(
    db: Session,
    *,
    source: str,
    model: str,
    response,
    human_user_id: int | None = None,
    post_id: int | None = None,
    actor: str | None = None,
) -> models.TokenUsage | None:
    """Records one API call's token usage on the caller's session (not committed).

    `source` is the spend driver ("bot_reaction" | "ad_tagline"); `actor` is the
    bot/advertiser name; `human_user_id` attributes the spend to the human whose
    post/feed triggered it. Never raises — metering is best-effort.
    """
    try:
        input_tokens, output_tokens = _tokens(response)
        row = models.TokenUsage(
            source=source,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd(model, input_tokens, output_tokens),
            human_user_id=human_user_id,
            post_id=post_id,
            actor=actor,
        )
        db.add(row)
        return row
    except Exception:
        logger.exception("failed to record token usage for %s", actor)
        return None
