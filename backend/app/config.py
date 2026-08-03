from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the project root (one level above backend/).
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://faceplant:faceplant@localhost:5433/faceplant"
    frontend_url: str = "http://localhost:5174"

    media_root: str = str(Path(__file__).resolve().parents[1] / "uploads")
    max_avatar_mb: float = 5.0

    admin_api_key: str
    anthropic_api_key: str = ""
    default_bot_model: str = "claude-haiku-4-5"
    # Used by GIF-first bot personas (roster entries with uses_giphy=True) to
    # fetch a random reaction GIF by tag. Optional: without it those bots fall
    # back to a caption-only reply.
    giphy_api_key: str = ""

    # Signs the session cookie issued after a magic-link login. Required, like
    # admin_api_key — generate with `python -c "import secrets; print(secrets.token_hex(32))"`.
    session_secret_key: str
    session_ttl_days: int = 30
    # Set True once served over real HTTPS; localhost dev stays False (http://).
    cookie_secure: bool = False

    magic_link_token_ttl_minutes: int = 15
    # Sends magic-link emails via Resend (https://resend.com). Optional: without
    # it, the link is logged to the backend console instead — no email account
    # needed for local dev.
    resend_api_key: str = ""
    email_from: str = "Faceplant <onboarding@resend.dev>"

    short_reaction_window_minutes: int = 5
    long_reaction_window_min_minutes: int = 15
    long_reaction_window_max_minutes: int = 180

    short_wave_size_min: int = 3
    short_wave_size_max: int = 5
    long_wave_size_min: int = 3
    long_wave_size_max: int = 5

    # Route bot reactions through the async Message Batches API (50% cheaper) instead
    # of one synchronous Claude call per reaction. Off by default. When on, a due wave
    # is submitted as one batch and its comments/likes/cost are written when the batch
    # ends (usually minutes at low volume) — a fit for the already-delayed reaction
    # waves. See reconcile_reaction_batches, polled separately by the scheduler.
    use_batch_api: bool = False

    # Prepend a large, shared "house style" block to every reaction's system prompt
    # and cache it (prompt caching). Off by default. The block is byte-identical
    # across all bots, so repeat reactions within the cache window read it at ~0.1x.
    # NOTE: it only actually caches when the shared prefix exceeds the model's minimum
    # cacheable size (4096 tokens on claude-haiku-4-5) AND is re-read inside the 5-min
    # TTL — so the payoff is real for bursty/high-volume swarms and nil for a lone,
    # widely-spaced reaction. Metering (usage.py) prices cache reads/writes correctly.
    use_prompt_caching: bool = False

    # "Dead internet": bots reacting to other bots' activity, so threads sustain
    # themselves with no humans. OFF by default — this is real, unbounded-by-
    # default Anthropic spend with no human in the loop. When enabled, the guard
    # rails below keep it from spiraling: waves decay by generation, stop at
    # max_reaction_generation, cap per thread, and halt entirely once cumulative
    # metered spend crosses global_spend_ceiling_usd. Inert while the flag is off.
    bots_react_to_bots: bool = False
    max_reaction_generation: int = 3
    max_reactions_per_thread: int = 40
    global_spend_ceiling_usd: float = 5.0  # 0 = unlimited (dangerous)

    # Phase 3: bots posting on their own, so a thread can start with no human in
    # it at all. Off by default; rate-limited to one bot-authored post per
    # bot_post_interval_minutes; also halts under the global spend ceiling.
    bot_origination_enabled: bool = False
    bot_post_interval_minutes: int = 10


settings = Settings()
