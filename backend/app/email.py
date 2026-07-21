import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def send_magic_link_email(to_email: str, link: str) -> None:
    """Emails the sign-in link via Resend, or logs it if no API key is set.

    The console fallback is what keeps local dev working with zero email
    setup; a failed real send also falls back to logging so a provider
    hiccup never silently strands a user without any way to find their link.
    """
    if not settings.resend_api_key:
        # warning, not info: this must be visible under default logging config
        # (root level is WARNING with no setup) since it's the only place the
        # link goes when there's no email provider configured.
        logger.warning("Magic link for %s (RESEND_API_KEY not set): %s", to_email, link)
        return

    subject = "Your faceplant sign-in link"
    html = (
        f'<p>Click to sign in to faceplant: <a href="{link}">{link}</a></p>'
        f"<p>This link expires in {settings.magic_link_token_ttl_minutes} minutes.</p>"
    )
    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.email_from, "to": [to_email], "subject": subject, "html": html},
            timeout=10.0,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to send magic link email to %s; link: %s", to_email, link)
