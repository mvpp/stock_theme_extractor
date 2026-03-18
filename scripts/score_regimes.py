#!/usr/bin/env python3
"""Regime scoring engine with upgrade/downgrade hysteresis.

Computes a composite 0-100 regime score from thematic + price signals,
clamps daily movement to +-5 points, and requires 3-day confirmation
for regime label transitions.

Run after refresh_prices.py and take_snapshot.py:
    python scripts/score_regimes.py --db stock_themes.db
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from themes_api.db import init_db  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score-to-label mapping
# ---------------------------------------------------------------------------

REGIME_BOUNDARIES = [20, 40, 60, 80]  # emergence|diffusion|consensus|monetization|decay
REGIME_LABELS = ["emergence", "diffusion", "consensus", "monetization", "decay"]
MAX_DAILY_DELTA = 5.0
WATCH_CONFIRM_DAYS = 3
WATCH_PROXIMITY = 3.0  # points from boundary to trigger watch


def score_to_label(score: float) -> str:
    for i, boundary in enumerate(REGIME_BOUNDARIES):
        if score < boundary:
            return REGIME_LABELS[i]
    return REGIME_LABELS[-1]


# ---------------------------------------------------------------------------
# Signal computation (9 signals, each normalized to 0-100)
# ---------------------------------------------------------------------------

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _map_range(val: float, in_lo: float, in_hi: float,
               out_lo: float = 0.0, out_hi: float = 100.0) -> float:
    """Linear map val from [in_lo, in_hi] to [out_lo, out_hi], clamped."""
    if in_hi == in_lo:
        return (out_lo + out_hi) / 2
    t = (val - in_lo) / (in_hi - in_lo)
    t = _clamp(t, 0, 1)
    return out_lo + t * (out_hi - out_lo)


def _slope(values: list[float]) -> float:
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


def compute_raw_score(conn: sqlite3.Connection, theme_name: str,
                      lookback_days: int = 90) -> tuple[float, dict]:
    """Compute the raw composite regime score from 9 signals.

    Returns (raw_score, signal_components_dict).
    """
    # --- Thematic signals from theme_snapshots ---
    snaps = conn.execute(
        """SELECT snapshot_date, stock_count, avg_confidence,
                  news_mention_count, source_breakdown
           FROM theme_snapshots
           WHERE theme_name = ? AND snapshot_date >= date('now', ?)
           ORDER BY snapshot_date""",
        (theme_name, f"-{lookback_days} days"),
    ).fetchall()

    # Defaults
    stock_count = 0
    avg_confidence = 0.0
    confidence_momentum_raw = 0.0
    news_momentum_raw = 0.0
    source_diversity = 1
    days_since_first = 999

    if snaps:
        latest = snaps[-1]
        stock_count = latest["stock_count"]
        avg_confidence = latest["avg_confidence"] or 0.0

        try:
            breakdown = json.loads(latest["source_breakdown"] or "{}")
            source_diversity = len(breakdown)
        except (json.JSONDecodeError, TypeError):
            source_diversity = 1

        if len(snaps) >= 2:
            confs = [s["avg_confidence"] or 0 for s in snaps]
            confidence_momentum_raw = _slope(confs)

        if len(snaps) >= 4:
            mid = len(snaps) // 2
            recent_news = sum((s["news_mention_count"] or 0) for s in snaps[mid:])
            earlier_news = sum((s["news_mention_count"] or 0) for s in snaps[:mid])
            news_momentum_raw = recent_news - earlier_news
    else:
        # Fallback: current state from live tables
        cur = conn.execute(
            """SELECT COUNT(*) AS cnt, AVG(st.confidence) AS avg_conf
               FROM stock_themes st
               JOIN themes t ON t.id = st.theme_id
               WHERE t.name = ?""",
            (theme_name,),
        ).fetchone()
        if cur:
            stock_count = cur["cnt"]
            avg_confidence = cur["avg_conf"] or 0.0

    # Age
    first = conn.execute(
        "SELECT MIN(snapshot_date) AS first_date FROM theme_snapshots WHERE theme_name = ?",
        (theme_name,),
    ).fetchone()
    if first and first["first_date"]:
        first_date = date.fromisoformat(first["first_date"])
        days_since_first = (date.today() - first_date).days

    # --- Price/technical signals from theme_technicals ---
    tech = conn.execute(
        """SELECT avg_ma20_distance_pct, pct_above_ma20, avg_volume_trend,
                  avg_analyst_upside_pct, avg_positive_surprises
           FROM theme_technicals
           WHERE theme_name = ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (theme_name,),
    ).fetchone()

    avg_ma20_dist = 0.0
    avg_vol_trend = 0.0
    avg_analyst_upside = 0.0
    avg_pos_surprises = 0.0

    if tech:
        avg_ma20_dist = tech["avg_ma20_distance_pct"] or 0.0
        avg_vol_trend = tech["avg_volume_trend"] or 0.0
        avg_analyst_upside = tech["avg_analyst_upside_pct"] or 0.0
        avg_pos_surprises = tech["avg_positive_surprises"] or 0.0

    # --- Normalize each signal to 0-100 ---
    signals = {
        "stock_count": _clamp(stock_count / 25, 0, 1) * 100,
        "confidence": avg_confidence * 100,
        "confidence_momentum": _map_range(confidence_momentum_raw, -0.01, 0.01),
        "news_momentum": _map_range(news_momentum_raw, -10, 10),
        "source_diversity": _clamp(source_diversity / 7, 0, 1) * 100,
        "age": _clamp(days_since_first / 180, 0, 1) * 100,
        "price_momentum": _map_range(avg_ma20_dist, -10, 10),
        "analyst_upside": _map_range(avg_analyst_upside, -20, 40, 100, 0),  # inverted
        "volume_trend": _map_range(avg_vol_trend, -1, 1),
    }

    # --- Weighted composite ---
    weights = {
        "stock_count": 0.10,
        "confidence": 0.10,
        "confidence_momentum": 0.10,
        "news_momentum": 0.10,
        "source_diversity": 0.10,
        "age": 0.05,
        "price_momentum": 0.20,
        "analyst_upside": 0.10,
        "volume_trend": 0.10,
    }
    # Remaining 5% for earnings quality
    earnings_quality = _clamp(avg_pos_surprises / 4, 0, 1) * 100
    signals["earnings_quality"] = earnings_quality
    weights["earnings_quality"] = 0.05

    raw_score = sum(signals[k] * weights[k] for k in weights)
    raw_score = _clamp(raw_score, 0, 100)

    # Round signals for storage
    signals = {k: round(v, 2) for k, v in signals.items()}

    return raw_score, signals


# ---------------------------------------------------------------------------
# Hysteresis: clamp + watch + confirm
# ---------------------------------------------------------------------------

def score_regime(conn: sqlite3.Connection, theme_name: str,
                 today_str: str, bootstrap: bool = False) -> dict:
    """Score a single theme with upgrade/downgrade hysteresis.

    Returns the regime_scores row dict.
    """
    raw_score, signals = compute_raw_score(conn, theme_name)

    # Get previous day's score
    prev = conn.execute(
        """SELECT regime_score, regime_label, regime_direction,
                  watch_status, watch_since
           FROM regime_scores
           WHERE theme_name = ? AND snapshot_date < ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (theme_name, today_str),
    ).fetchone()

    if prev is None or bootstrap:
        # First run — use raw score directly
        label = score_to_label(raw_score)
        return {
            "theme_name": theme_name,
            "snapshot_date": today_str,
            "regime_score": round(raw_score, 2),
            "regime_label": label,
            "regime_direction": "stable",
            "watch_status": None,
            "watch_since": None,
            "signal_components": json.dumps(signals),
        }

    prev_score = prev["regime_score"]
    prev_label = prev["regime_label"]
    prev_watch = prev["watch_status"]
    prev_watch_since = prev["watch_since"]

    # Clamp daily movement
    delta = _clamp(raw_score - prev_score, -MAX_DAILY_DELTA, MAX_DAILY_DELTA)
    new_score = _clamp(prev_score + delta, 0, 100)

    # Determine tentative label
    tentative_label = score_to_label(new_score)

    # Hysteresis logic
    final_label = prev_label
    watch_status = prev_watch
    watch_since = prev_watch_since

    if tentative_label != prev_label:
        # Score crossed a boundary
        if prev_watch is not None and prev_watch_since is not None:
            # Already on watch — check confirmation
            watch_start = date.fromisoformat(prev_watch_since)
            days_on_watch = (date.fromisoformat(today_str) - watch_start).days
            raw_label = score_to_label(raw_score)
            if days_on_watch >= WATCH_CONFIRM_DAYS and raw_label == tentative_label:
                # Confirmed transition
                final_label = tentative_label
                watch_status = None
                watch_since = None
            else:
                # Still watching — keep old label
                final_label = prev_label
        else:
            # Start watching
            direction = "upgrade_watch" if new_score > prev_score else "downgrade_watch"
            watch_status = direction
            watch_since = today_str
            final_label = prev_label
    else:
        # Same label — clear any watch
        watch_status = None
        watch_since = None
        final_label = tentative_label

    # Direction based on recent trend
    direction = "stable"
    if abs(delta) >= 1:
        direction = "upgrading" if delta > 0 else "downgrading"

    return {
        "theme_name": theme_name,
        "snapshot_date": today_str,
        "regime_score": round(new_score, 2),
        "regime_label": final_label,
        "regime_direction": direction,
        "watch_status": watch_status,
        "watch_since": watch_since,
        "signal_components": json.dumps(signals),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Regime scoring with hysteresis")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--bootstrap", action="store_true",
                        help="Bootstrap mode: use raw scores without clamping")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    conn = init_db(args.db)
    today_str = date.today().isoformat()

    # Get all canonical themes
    themes = conn.execute("SELECT DISTINCT name FROM themes").fetchall()
    theme_names = [r["name"] for r in themes]
    logger.info("Scoring %d themes", len(theme_names))

    for theme_name in theme_names:
        result = score_regime(conn, theme_name, today_str, bootstrap=args.bootstrap)
        conn.execute(
            """INSERT OR REPLACE INTO regime_scores
               (theme_name, snapshot_date, regime_score, regime_label,
                regime_direction, watch_status, watch_since, signal_components)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (result["theme_name"], result["snapshot_date"],
             result["regime_score"], result["regime_label"],
             result["regime_direction"], result["watch_status"],
             result["watch_since"], result["signal_components"]),
        )

    # Record pipeline run
    conn.execute(
        "INSERT OR REPLACE INTO pipeline_runs "
        "(pipeline_name, run_date, status, tickers_processed, tickers_failed, "
        "error_message, completed_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("regime_pipeline", today_str, "success", len(theme_names), 0, None),
    )
    conn.commit()
    conn.close()
    logger.info("Regime scoring complete for %d themes", len(theme_names))


if __name__ == "__main__":
    main()
