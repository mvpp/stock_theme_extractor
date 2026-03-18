"""Theme lifecycle regime classification.

Regimes: Emergence → Diffusion → Consensus → Monetization → Decay
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass
class RegimeSignals:
    """Computed signals used to classify a theme's lifecycle regime."""
    theme_name: str
    stock_count: int = 0
    stock_count_velocity: float = 0.0
    confidence_trend: float = 0.0
    news_trend: float = 0.0
    news_density: int = 0
    source_diversity: int = 0
    days_since_first_seen: int = 999
    avg_confidence: float = 0.0


REGIME_COLORS = {
    "emergence": "#22c55e",
    "diffusion": "#3b82f6",
    "consensus": "#f59e0b",
    "monetization": "#a855f7",
    "decay": "#ef4444",
}


def classify_regime(signals: RegimeSignals) -> str:
    """Classify a theme into a lifecycle regime based on computed signals."""
    if signals.days_since_first_seen < 30:
        return "emergence"
    if signals.stock_count <= 5 and signals.stock_count_velocity > 0:
        return "emergence"

    if (signals.stock_count_velocity < -0.01
            and signals.confidence_trend < -0.001
            and signals.news_trend < 0):
        return "decay"

    if (signals.stock_count > 15
            and signals.avg_confidence > 0.7
            and abs(signals.stock_count_velocity) < 0.05):
        return "monetization"

    if (signals.stock_count > 20
            and signals.source_diversity >= 3):
        return "consensus"

    if (signals.stock_count_velocity > 0
            and signals.confidence_trend >= 0
            and 5 < signals.stock_count <= 20):
        return "diffusion"

    return "diffusion"


def compute_signals(conn: sqlite3.Connection, theme_name: str,
                    lookback_days: int = 90) -> RegimeSignals:
    """Compute regime signals for a single theme from snapshot history."""
    snaps = conn.execute(
        """SELECT snapshot_date, stock_count, avg_confidence,
                  news_mention_count, source_breakdown
           FROM theme_snapshots
           WHERE theme_name = ? AND snapshot_date >= date('now', ?)
           ORDER BY snapshot_date""",
        (theme_name, f"-{lookback_days} days"),
    ).fetchall()

    signals = RegimeSignals(theme_name=theme_name)

    if not snaps:
        cur = conn.execute(
            """SELECT COUNT(*) AS cnt, AVG(st.confidence) AS avg_conf
               FROM stock_themes st
               JOIN themes t ON t.id = st.theme_id
               WHERE t.name = ?""",
            (theme_name,),
        ).fetchone()
        if cur:
            signals.stock_count = cur["cnt"]
            signals.avg_confidence = cur["avg_conf"] or 0.0
        return signals

    latest = snaps[-1]
    signals.stock_count = latest["stock_count"]
    signals.avg_confidence = latest["avg_confidence"] or 0.0
    signals.news_density = latest["news_mention_count"] or 0

    try:
        breakdown = json.loads(latest["source_breakdown"] or "{}")
        signals.source_diversity = len(breakdown)
    except (json.JSONDecodeError, TypeError):
        signals.source_diversity = 1

    first = conn.execute(
        "SELECT MIN(snapshot_date) AS first_date FROM theme_snapshots WHERE theme_name = ?",
        (theme_name,),
    ).fetchone()
    if first and first["first_date"]:
        from datetime import date
        first_date = date.fromisoformat(first["first_date"])
        signals.days_since_first_seen = (date.today() - first_date).days

    if len(snaps) >= 2:
        counts = [s["stock_count"] for s in snaps]
        confs = [s["avg_confidence"] or 0 for s in snaps]
        signals.stock_count_velocity = _slope(counts)
        signals.confidence_trend = _slope(confs)

    if len(snaps) >= 4:
        mid = len(snaps) // 2
        recent_news = sum((s["news_mention_count"] or 0) for s in snaps[mid:])
        earlier_news = sum((s["news_mention_count"] or 0) for s in snaps[:mid])
        signals.news_trend = recent_news - earlier_news

    return signals


def classify_regime_batch(conn: sqlite3.Connection,
                          lookback_days: int = 90) -> dict[str, str]:
    """Classify regimes for all themes with snapshots."""
    themes = conn.execute(
        "SELECT DISTINCT theme_name FROM theme_snapshots"
    ).fetchall()

    result = {}
    for row in themes:
        name = row["theme_name"]
        signals = compute_signals(conn, name, lookback_days)
        result[name] = classify_regime(signals)
    return result


def _slope(values: list[float]) -> float:
    """Simple linear regression slope."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    sum_x = sum(xs)
    sum_y = sum(values)
    sum_xy = sum(x * y for x, y in zip(xs, values))
    sum_xx = sum(x * x for x in xs)
    denom = n * sum_xx - sum_x ** 2
    return (n * sum_xy - sum_x * sum_y) / denom if denom else 0.0
