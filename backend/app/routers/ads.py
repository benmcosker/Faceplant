from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..ads.targeting import build_tagline, select_ad
from ..auth import get_current_user
from ..db import get_db
from ..schemas import AdOut

router = APIRouter(prefix="/api", tags=["ads"])


@router.get("/sponsored", response_model=AdOut)
def get_sponsored(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """The 'sponsored' post targeted at this viewer's profiled mood.

    Real platforms always have an ad to show — so does this one. If we haven't
    profiled the user yet (no posts), they get the deliberately hollow neutral
    ad. The tagline is personalized against the user's most recent post.
    """
    mood = user.mood or "neutral"
    ad = select_ad(mood)

    latest_post = (
        db.query(models.Post)
        .filter(models.Post.user_id == user.id)
        .order_by(models.Post.id.desc())
        .first()
    )
    tagline = build_tagline(
        ad,
        latest_post.body if latest_post else "",
        mood,
        db=db,
        human_user_id=user.id,
        post_id=latest_post.id if latest_post else None,
    )
    # build_tagline may have recorded ad-generation token usage on this session.
    db.commit()

    return AdOut(
        advertiser=ad["advertiser"],
        tagline=tagline,
        body=ad["body"],
        cta=ad["cta"],
        mood=mood,
        url=ad["url"],
    )
