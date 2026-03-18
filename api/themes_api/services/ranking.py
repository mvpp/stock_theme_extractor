"""Theme ranking service — top themes by volume, momentum, or stock count."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from themes_api.db import init_db


def get_top_themes(
    db_path: str | Path,
    sort_by: str = "stock_count",
    limit: int = 10,
    lookback_days: int = 90,
) -> list[dict]:
    conn = init_db(db_path)

    current = conn.execute(
        """SELECT t.name AS theme_name, t.category,
                  COUNT(*) AS stock_count,
                  SUM(s.market_cap) AS total_market_cap,
                  AVG(st.confidence) AS avg_confidence
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           JOIN stocks s ON s.ticker = st.ticker
           GROUP BY t.name"""
    ).fetchall()
    current_map = {r["theme_name"]: dict(r) for r in current}

    if sort_by == "momentum":
        snap_rows = conn.execute(
            """SELECT theme_name, snapshot_date, stock_count
               FROM theme_snapshots
               WHERE snapshot_date >= date('now', ?)
               ORDER BY theme_name, snapshot_date""",
            (f"-{lookback_days} days",),
        ).fetchall()

        series: dict[str, list[tuple[int, int]]] = {}
        for row in snap_rows:
            name = row["theme_name"]
            if name not in series:
                series[name] = []
            series[name].append((len(series[name]), row["stock_count"]))

        momentum_map: dict[str, float] = {}
        for name, points in series.items():
            if len(points) < 2:
                momentum_map[name] = 0.0
                continue
            n = len(points)
            sum_x = sum(p[0] for p in points)
            sum_y = sum(p[1] for p in points)
            sum_xy = sum(p[0] * p[1] for p in points)
            sum_xx = sum(p[0] ** 2 for p in points)
            denom = n * sum_xx - sum_x ** 2
            momentum_map[name] = (n * sum_xy - sum_x * sum_y) / denom if denom else 0.0

        for name, info in current_map.items():
            info["momentum"] = momentum_map.get(name, 0.0)
    else:
        for info in current_map.values():
            info["momentum"] = 0.0

    regime_map = _get_latest_regimes(conn, lookback_days)

    results = []
    for name, info in current_map.items():
        results.append({
            "theme_name": name,
            "category": info["category"],
            "stock_count": info["stock_count"],
            "total_market_cap": info["total_market_cap"] or 0,
            "avg_confidence": info["avg_confidence"],
            "momentum": info["momentum"],
            "regime": regime_map.get(name, "diffusion"),
        })

    sort_key = {
        "stock_count": lambda x: x["stock_count"],
        "volume": lambda x: x["total_market_cap"],
        "momentum": lambda x: x["momentum"],
    }.get(sort_by, lambda x: x["stock_count"])

    results.sort(key=sort_key, reverse=True)
    conn.close()
    return results[:limit]


def _get_latest_regimes(conn: sqlite3.Connection, lookback_days: int) -> dict[str, str]:
    from themes_api.services.regime import classify_regime_batch
    return classify_regime_batch(conn, lookback_days)
