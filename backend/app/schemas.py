from datetime import datetime

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    username: str
    avatar_url: str
    is_bot: bool

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    username: str
    body: str = Field(min_length=1, max_length=2000)


class CommentCreate(BaseModel):
    username: str
    body: str = Field(min_length=1, max_length=2000)


class LikeToggle(BaseModel):
    username: str


class CommentOut(BaseModel):
    id: int
    body: str
    created_at: datetime
    author: UserOut


class PostOut(BaseModel):
    id: int
    body: str
    created_at: datetime
    author: UserOut
    like_count: int
    comment_count: int


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


class SourceCost(BaseModel):
    cost_usd: float
    calls: int


class UserCost(BaseModel):
    username: str
    cost_usd: float
    calls: int


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


class AdminBotCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)
    persona: str
    model: str | None = None
    avatar_url: str
