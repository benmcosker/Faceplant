from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: int
    username: str
    avatar_url: str
    is_bot: bool

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class RequestLinkIn(BaseModel):
    email: EmailStr


class VerifyIn(BaseModel):
    token: str


class VerifyOut(BaseModel):
    """`status` is "logged_in" (session set, `user` populated) or "new" (email
    verified but no account yet — `email` populated, frontend collects a
    username + avatar and calls /api/auth/signup)."""

    status: str
    user: UserOut | None = None
    email: str | None = None


class CommentOut(BaseModel):
    id: int
    body: str
    created_at: datetime
    author: UserOut


class ThreadStats(BaseModel):
    """How human a thread is, measured by message (post + comments). Powers the
    live "% human" counter — the "dead internet" gut-punch."""

    # human_messages / total_messages, 0.0–1.0. 1.0 = all human, 0.0 = no humans.
    human_share: float
    human_messages: int
    bot_messages: int
    total_messages: int


class PostOut(BaseModel):
    id: int
    body: str
    created_at: datetime
    author: UserOut
    like_count: int
    comment_count: int
    # The first few replies, for an inline "peek" of the swarm in the feed.
    top_comments: list[CommentOut] = []
    # How human this thread is, by message count — the "% human" counter.
    human_share: float = 1.0
    human_messages: int = 1
    bot_messages: int = 0
    total_messages: int = 1


class LikeResult(BaseModel):
    liked: bool
    count: int


class AdOut(BaseModel):
    advertiser: str
    tagline: str
    body: str
    cta: str
    # The mood the viewer was profiled into — shown on the card's targeting banner.
    mood: str
    # Where the CTA links out (a real brand / affiliate URL). Opened with
    # rel="sponsored nofollow noopener".
    url: str


class SourceCost(BaseModel):
    cost_usd: float
    calls: int


class UserCost(BaseModel):
    username: str
    cost_usd: float
    calls: int


class SpendEvent(BaseModel):
    """One metered API call, for the live recent-spend ticker."""

    source: str
    # The bot or advertiser that did the spending.
    actor: str | None
    # The human whose engagement it was manufacturing.
    human_username: str | None
    cost_usd: float
    created_at: datetime


class CostSummary(BaseModel):
    """"The Meter": the running estimated Claude spend behind the feed."""

    total_cost_usd: float
    total_calls: int
    input_tokens: int
    output_tokens: int
    # Spend split by driver: "bot_reaction" (the swarm) vs "ad_tagline" (the ad network).
    by_source: dict[str, SourceCost]
    # Cost attributed to each human whose posts/feed triggered the spend.
    per_human_user: list[UserCost]
    human_user_count: int
    cost_per_human_user_avg: float
    # Storytelling layer: derived rates + a live feed of recent spend.
    cost_per_post_usd: float
    rate_per_min_usd: float
    # Most recent metered calls, newest first.
    recent: list[SpendEvent]
    # Spend bucketed into one-minute windows, oldest -> newest, for a sparkline.
    spend_per_min: list[float]
    # Spend with no human at either end (bot-authored posts + bots reacting to
    # bots) — manufactured engagement serving nobody. "The void".
    no_human_cost_usd: float = 0.0
    no_human_calls: int = 0


class AdminBotCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)
    persona: str
    model: str | None = None
    avatar_url: str
