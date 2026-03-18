"""Theme lifecycle regime — reads from precomputed regime_scores table.

Regimes: Emergence → Diffusion → Consensus → Monetization → Decay

The regime score (0-100) is computed by scripts/score_regimes.py with
upgrade/downgrade hysteresis.  This module provides read access and
a fallback raw-score computation for themes without stored scores.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


REGIME_COLORS = {
    "emergence": "#22c55e",
    "diffusion": "#3b82f6",
    "consensus": "#f59e0b",
    "monetization": "#a855f7",
    "decay": "#ef4444",
}


@dataclass
class RegimeResult:
    theme_name: str
    regime_score: float
    regime_label: str
    regime_direction: str
    watch_status: str | None
    color: str
    signals: dict
    raw_score: float | None = None


def get_regime(conn: sqlite3.Connection, theme_name: str) -> RegimeResult:
    """Get the latest regime score for a theme.

    Reads from regime_scores table.  Falls back to a simple on-the-fly
    computation if no stored score exists (e.g. brand-new theme).
    """
    row = conn.execute(
        """SELECT regime_score, regime_label, regime_direction,
                  watch_status, signal_components
           FROM regime_scores
           WHERE theme_name = ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (theme_name,),
    ).fetchone()

    if row:
        signals = {}
        try:
            signals = json.loads(row["signal_components"] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass

        label = row["regime_label"]
        return RegimeResult(
            theme_name=theme_name,
            regime_score=row["regime_score"],
            regime_label=label,
            regime_direction=row["regime_direction"],
            watch_status=row["watch_status"],
            color=REGIME_COLORS.get(label, "#6b7280"),
            signals=signals,
        )

    # Fallback: compute raw score on the fly (no hysteresis)
    return _fallback_regime(conn, theme_name)


def get_regime_batch(conn: sqlite3.Connection) -> dict[str, RegimeResult]:
    """Get latest regime for all themes that have stored scores."""
    rows = conn.execute(
        """SELECT rs.theme_name, rs.regime_score, rs.regime_label,
                  rs.regime_direction, rs.watch_status, rs.signal_components
           FROM regime_scores rs
           INNER JOIN (
               SELECT theme_name, MAX(snapshot_date) AS max_date
               FROM regime_scores GROUP BY theme_name
           ) latest ON rs.theme_name = latest.theme_name
                    AND rs.snapshot_date = latest.max_date"""
    ).fetchall()

    result = {}
    for row in rows:
        label = row["regime_label"]
        signals = {}
        try:
            signals = json.loads(row["signal_components"] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        result[row["theme_name"]] = RegimeResult(
            theme_name=row["theme_name"],
            regime_score=row["regime_score"],
            regime_label=label,
            regime_direction=row["regime_direction"],
            watch_status=row["watch_status"],
            color=REGIME_COLORS.get(label, "#6b7280"),
            signals=signals,
        )
    return result


def get_regime_history(conn: sqlite3.Connection, theme_name: str,
                       days: int = 90) -> list[dict]:
    """Return regime score time series for charting."""
    rows = conn.execute(
        """SELECT snapshot_date, regime_score, regime_label,
                  regime_direction, watch_status
           FROM regime_scores
           WHERE theme_name = ? AND snapshot_date >= date('now', ?)
           ORDER BY snapshot_date""",
        (theme_name, f"-{days} days"),
    ).fetchall()
    return [dict(r) for r in rows]


def _fallback_regime(conn: sqlite3.Connection, theme_name: str) -> RegimeResult:
    """Simple fallback for themes without stored regime_scores."""
    cur = conn.execute(
        """SELECT COUNT(*) AS cnt, AVG(st.confidence) AS avg_conf
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           WHERE t.name = ?""",
        (theme_name,),
    ).fetchone()

    stock_count = cur["cnt"] if cur else 0
    avg_conf = cur["avg_conf"] or 0.0 if cur else 0.0

    # Very rough estimate based on available data
    score = min(stock_count / 25, 1) * 50 + avg_conf * 50
    score = max(0, min(100, score))
    label = _score_to_label(score)

    return RegimeResult(
        theme_name=theme_name,
        regime_score=round(score, 2),
        regime_label=label,
        regime_direction="stable",
        watch_status=None,
        color=REGIME_COLORS.get(label, "#6b7280"),
        signals={"stock_count": stock_count, "confidence": round(avg_conf * 100, 2)},
    )


def _score_to_label(score: float) -> str:
    boundaries = [20, 40, 60, 80]
    labels = ["emergence", "diffusion", "consensus", "monetization", "decay"]
    for i, b in enumerate(boundaries):
        if score < b:
            return labels[i]
    return labels[-1]
