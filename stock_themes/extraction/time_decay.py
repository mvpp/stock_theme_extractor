"""Time decay scoring for news articles and themes.

Articles < fresh_days old get full weight (1.0).
Articles > stale_days old get zero weight (0.0).
In between, a half-cosine curve smoothly decays from 1.0 to 0.0.
"""

from __future__ import annotations

import math
from datetime import datetime

from stock_themes.config import DECAY_FRESH_DAYS, DECAY_STALE_DAYS
from stock_themes.models import DatedArticle


def compute_decay(
    published_at: datetime | None,
    reference: datetime | None = None,
    fresh_days: int | None = None,
    stale_days: int | None = None,
) -> float:
    """Return a decay multiplier in [0.0, 1.0].

    Args:
        published_at: When the article was published. None -> 0.5 (unknown).
        reference: Reference date (default: utcnow).
        fresh_days: Days within which content is fully fresh.
        stale_days: Days after which content is fully stale.
    """
    if published_at is None:
        return 0.5  # unknown date — half weight

    if reference is None:
        reference = datetime.utcnow()

    age_days = (reference - published_at).total_seconds() / 86400.0
    if age_days < 0:
        return 1.0  # future date (clock skew) — treat as fresh

    _fresh = fresh_days if fresh_days is not None else DECAY_FRESH_DAYS
    _stale = stale_days if stale_days is not None else DECAY_STALE_DAYS

    if age_days <= _fresh:
        return 1.0
    if age_days >= _stale:
        return 0.0

    # Half-cosine decay between fresh and stale boundaries
    progress = (age_days - _fresh) / (_stale - _fresh)
    return 0.5 * (1.0 + math.cos(math.pi * progress))


def freshness_score(articles: list[DatedArticle]) -> float:
    """Average decay weight across all articles.

    Returns 1.0 if all articles are fresh, 0.0 if all are stale.
    Returns 0.5 if no articles provided (unknown freshness).
    """
    if not articles:
        return 0.5

    now = datetime.utcnow()
    weights = [compute_decay(a.published_at, reference=now) for a in articles]
    return sum(weights) / len(weights)


def weighted_articles(
    articles: list[DatedArticle],
) -> list[tuple[DatedArticle, float]]:
    """Return articles paired with their decay weight, sorted by recency."""
    now = datetime.utcnow()
    paired = [(a, compute_decay(a.published_at, reference=now)) for a in articles]
    # Sort by recency (most recent first); articles without dates go last
    paired.sort(
        key=lambda t: t[0].published_at or datetime.min,
        reverse=True,
    )
    return paired
