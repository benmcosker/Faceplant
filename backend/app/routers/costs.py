from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..schemas import CostSummary, SourceCost, SpendEvent, UserCost

router = APIRouter(prefix="/api", tags=["costs"])

# How far back the $/min sparkline reaches, and its bucket size.
SPARKLINE_BUCKETS = 15
BUCKET_SECONDS = 60
# How many recent calls the ticker shows.
RECENT_LIMIT = 8


@router.get("/costs", response_model=CostSummary)
def get_costs(db: Session = Depends(get_db)):
    """The running estimated Claude spend behind the feed — "The Meter".

    Aggregates every recorded API call: totals, a swarm-vs-ads breakdown, a
    per-human-user attribution, plus a storytelling layer — cost per post, the
    live $/min spend rate, a recent-spend ticker, and a per-minute sparkline.
    """
    rows = db.query(models.TokenUsage).all()

    now = datetime.utcnow()
    window_start = now - timedelta(seconds=SPARKLINE_BUCKETS * BUCKET_SECONDS)
    rate_start = now - timedelta(seconds=BUCKET_SECONDS)

    total_cost = 0.0
    input_tokens = 0
    output_tokens = 0
    by_source: dict[str, dict] = {}
    per_user: dict[int, dict] = {}
    nobody = {"cost_usd": 0.0, "calls": 0}
    post_ids: set[int] = set()
    rate_per_min = 0.0
    buckets = [0.0] * SPARKLINE_BUCKETS

    for row in rows:
        total_cost += row.cost_usd
        input_tokens += row.input_tokens
        output_tokens += row.output_tokens

        src = by_source.setdefault(row.source, {"cost_usd": 0.0, "calls": 0})
        src["cost_usd"] += row.cost_usd
        src["calls"] += 1

        if row.human_user_id is not None:
            u = per_user.setdefault(row.human_user_id, {"cost_usd": 0.0, "calls": 0})
            u["cost_usd"] += row.cost_usd
            u["calls"] += 1
        else:
            # No human at either end (a bot-authored post) — spend for the void.
            nobody["cost_usd"] += row.cost_usd
            nobody["calls"] += 1

        if row.post_id is not None:
            post_ids.add(row.post_id)

        created = row.created_at or now
        if created >= rate_start:
            rate_per_min += row.cost_usd
        if created >= window_start:
            idx = int((created - window_start).total_seconds() // BUCKET_SECONDS)
            if 0 <= idx < SPARKLINE_BUCKETS:
                buckets[idx] += row.cost_usd

    # Resolve human usernames once for both the per-user rollup and the ticker.
    referenced_ids = set(per_user.keys())
    recent_rows = sorted(rows, key=lambda r: (r.created_at or now, r.id), reverse=True)[:RECENT_LIMIT]
    referenced_ids.update(r.human_user_id for r in recent_rows if r.human_user_id is not None)

    users_by_id: dict[int, models.User] = {}
    if referenced_ids:
        users_by_id = {
            u.id: u for u in db.query(models.User).filter(models.User.id.in_(referenced_ids))
        }
    usernames = {uid: u.username for uid, u in users_by_id.items()}

    # Spend attributed to a bot (a bot's own post being swarmed) serves no human
    # either — fold it into "nobody" so the per-human rollup stays humans-only.
    for uid in list(per_user.keys()):
        user = users_by_id.get(uid)
        if user is None or user.is_bot:
            nobody["cost_usd"] += per_user[uid]["cost_usd"]
            nobody["calls"] += per_user[uid]["calls"]
            del per_user[uid]

    per_human_user = sorted(
        (
            UserCost(
                username=usernames.get(uid, "unknown"),
                cost_usd=round(v["cost_usd"], 6),
                calls=v["calls"],
            )
            for uid, v in per_user.items()
        ),
        key=lambda uc: uc.cost_usd,
        reverse=True,
    )
    human_user_count = len(per_user)

    recent = [
        SpendEvent(
            source=r.source,
            actor=r.actor,
            human_username=usernames.get(r.human_user_id) if r.human_user_id is not None else None,
            cost_usd=round(r.cost_usd, 6),
            created_at=r.created_at or now,
        )
        for r in recent_rows
    ]

    return CostSummary(
        total_cost_usd=round(total_cost, 6),
        total_calls=len(rows),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        by_source={
            source: SourceCost(cost_usd=round(v["cost_usd"], 6), calls=v["calls"])
            for source, v in by_source.items()
        },
        per_human_user=per_human_user,
        human_user_count=human_user_count,
        cost_per_human_user_avg=round(total_cost / human_user_count, 6) if human_user_count else 0.0,
        cost_per_post_usd=round(total_cost / len(post_ids), 6) if post_ids else 0.0,
        rate_per_min_usd=round(rate_per_min, 6),
        recent=recent,
        spend_per_min=[round(b, 6) for b in buckets],
        no_human_cost_usd=round(nobody["cost_usd"], 6),
        no_human_calls=nobody["calls"],
    )
