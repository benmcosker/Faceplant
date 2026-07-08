from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    avatar_url: Mapped[str] = mapped_column(String)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    # Humans never set one; bots get a hashed password when constructed via
    # the admin endpoint, mainly so the account has real credentials even
    # though nothing in the public UI logs in as a bot today.
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # Short voice/leaning description, e.g. "obvious bot", "earnest liberal".
    persona: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which LLM generates this bot's reactions, e.g. "claude-haiku-4-5".
    bot_model: Mapped[str | None] = mapped_column(String, nullable=True)
    # The platform's surveillance profile: the emotional tone of this user's most
    # recent post, classified on each post and used to target "sponsored" ads.
    mood: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_like_post_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BotReactionJob(Base):
    """A scheduled in-persona reaction to a post, polled and executed by the worker."""

    __tablename__ = "bot_reaction_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    bot_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TokenUsage(Base):
    """One recorded Claude API call: what it cost and who triggered it.

    Powers "The Meter" — the running cost of manufactured engagement. `source`
    is the spend driver ("bot_reaction" | "ad_tagline"); `human_user_id`
    attributes the spend to the human whose post/feed set it off.
    """

    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    # The human whose post (bot reactions) or feed (ad taglines) triggered the
    # spend. Nullable so an untriggered/unknown call is still recorded.
    human_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"), nullable=True)
    # The bot or advertiser that spent the tokens.
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
