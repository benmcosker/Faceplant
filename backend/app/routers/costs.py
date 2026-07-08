from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..schemas import CostSummary, SourceCost, UserCost

router = APIRouter(prefix="/api", tags=["costs"])


@router.get("/costs", response_model=CostSummary)
def get_costs(db: Session = Depends(get_db)):
    """The running estimated Claude spend behind the feed — "The Meter".

    Aggregates every recorded API call: totals, a swarm-vs-ads breakdown, and a
    per-human-user attribution so the cost of manufacturing each person's
    engagement is visible.
    """
    rows = db.query(models.TokenUsage).all()

    total_cost = 0.0
    input_tokens = 0
    output_tokens = 0
    by_source: dict[str, dict] = {}
    per_user: dict[int, dict] = {}

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

    usernames: dict[int, str] = {}
    if per_user:
        usernames = {
            u.id: u.username
            for u in db.query(models.User).filter(models.User.id.in_(per_user.keys()))
        }

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
    )
