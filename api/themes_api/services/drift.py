"""Drift detection — tracks how a theme's stock basket and sub-theme distribution change."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from themes_api.db import init_db


def compute_drift(
    db_path: str | Path,
    theme_name: str,
    days: int = 90,
) -> dict:
    """Compute drift analysis for a theme over the given lookback window."""
    conn = init_db(db_path)
    today = date.today()
    t0 = (today - timedelta(days=days)).isoformat()
    t1 = today.isoformat()

    earliest = conn.execute(
        """SELECT snapshot_date FROM theme_stock_snapshots
           WHERE theme_name = ? AND snapshot_date >= ?
           ORDER BY snapshot_date LIMIT 1""",
        (theme_name, t0),
    ).fetchone()

    latest = conn.execute(
        """SELECT snapshot_date FROM theme_stock_snapshots
           WHERE theme_name = ? AND snapshot_date <= ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (theme_name, t1),
    ).fetchone()

    if not earliest or not latest:
        conn.close()
        return {
            "theme_name": theme_name,
            "drift_score": 0.0,
            "period": {"from": t0, "to": t1},
            "entrants": [],
            "exits": [],
            "weekly_drift": [],
            "sub_theme_shift": {},
        }

    t0_date = earliest["snapshot_date"]
    t1_date = latest["snapshot_date"]

    s0 = _get_tickers_at(conn, theme_name, t0_date)
    s1 = _get_tickers_at(conn, theme_name, t1_date)

    union = s0 | s1
    intersection = s0 & s1
    drift_score = 1.0 - (len(intersection) / len(union)) if union else 0.0

    entrants = sorted(s1 - s0)
    exits = sorted(s0 - s1)

    weekly = _weekly_drift_series(conn, theme_name, t0_date, t1_date)
    sub_shift = _sub_theme_shift(conn, theme_name, t0_date, t1_date)

    conn.close()

    return {
        "theme_name": theme_name,
        "drift_score": round(drift_score, 4),
        "period": {"from": t0_date, "to": t1_date},
        "entrants": entrants,
        "exits": exits,
        "weekly_drift": weekly,
        "sub_theme_shift": sub_shift,
    }


def _get_tickers_at(conn: sqlite3.Connection, theme_name: str,
                    snap_date: str) -> set[str]:
    rows = conn.execute(
        """SELECT ticker FROM theme_stock_snapshots
           WHERE theme_name = ? AND snapshot_date = ?""",
        (theme_name, snap_date),
    ).fetchall()
    return {r["ticker"] for r in rows}


def _weekly_drift_series(conn: sqlite3.Connection, theme_name: str,
                         t0_date: str, t1_date: str) -> list[dict]:
    dates = conn.execute(
        """SELECT DISTINCT snapshot_date FROM theme_stock_snapshots
           WHERE theme_name = ? AND snapshot_date BETWEEN ? AND ?
           ORDER BY snapshot_date""",
        (theme_name, t0_date, t1_date),
    ).fetchall()
    dates = [r["snapshot_date"] for r in dates]

    if len(dates) < 2:
        return []

    baseline = _get_tickers_at(conn, theme_name, dates[0])
    result = []

    step = max(1, len(dates) // 12)
    for i in range(0, len(dates), step):
        current = _get_tickers_at(conn, theme_name, dates[i])
        union = baseline | current
        intersection = baseline & current
        jaccard = 1.0 - (len(intersection) / len(union)) if union else 0.0
        result.append({"date": dates[i], "jaccard": round(jaccard, 4)})

    return result


def _sub_theme_shift(conn: sqlite3.Connection, theme_name: str,
                     t0_date: str, t1_date: str) -> dict:
    """For parent themes, show how child theme distribution changed."""
    try:
        from themes_api.taxonomy import get_theme_tree
        tree = get_theme_tree()
        children = tree.get_descendants(theme_name) if theme_name in tree else []
    except Exception:
        children = []

    if not children:
        return {}

    shift = {}
    for child in children:
        t0_stocks = _get_tickers_at(conn, child, t0_date)
        t1_stocks = _get_tickers_at(conn, child, t1_date)
        if t0_stocks or t1_stocks:
            shift[child] = {
                "t0_count": len(t0_stocks),
                "t1_count": len(t1_stocks),
            }

    t0_total = sum(v["t0_count"] for v in shift.values()) or 1
    t1_total = sum(v["t1_count"] for v in shift.values()) or 1
    for child, v in shift.items():
        v["t0_pct"] = round(v["t0_count"] / t0_total, 3)
        v["t1_pct"] = round(v["t1_count"] / t1_total, 3)

    return shift
