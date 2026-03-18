"""Daily snapshot service — captures theme aggregate metrics and stock membership."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from themes_api.db import init_db


def take_snapshot(db_path: str | Path, snapshot_date: str | None = None) -> dict:
    """Capture current theme state into snapshot tables."""
    conn = init_db(db_path)
    snap_date = snapshot_date or date.today().isoformat()

    theme_rows = conn.execute(
        """SELECT t.name AS theme_name,
                  COUNT(*) AS stock_count,
                  SUM(s.market_cap) AS total_market_cap,
                  AVG(st.confidence) AS avg_confidence,
                  GROUP_CONCAT(DISTINCT st.source) AS sources
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           JOIN stocks s ON s.ticker = st.ticker
           GROUP BY t.name"""
    ).fetchall()

    freshness_map: dict[str, float] = {}
    fresh_rows = conn.execute(
        """SELECT mapped_canonical, AVG(freshness) AS avg_fresh
           FROM open_themes
           WHERE mapped_canonical IS NOT NULL AND freshness IS NOT NULL
           GROUP BY mapped_canonical"""
    ).fetchall()
    for r in fresh_rows:
        freshness_map[r["mapped_canonical"]] = r["avg_fresh"]

    news_map: dict[str, int] = {}
    news_rows = conn.execute(
        """SELECT mapped_canonical, COUNT(*) AS cnt
           FROM open_themes
           WHERE source = 'narrative' AND mapped_canonical IS NOT NULL
           GROUP BY mapped_canonical"""
    ).fetchall()
    for r in news_rows:
        news_map[r["mapped_canonical"]] = r["cnt"]

    theme_count = 0
    pair_count = 0

    with conn:
        for row in theme_rows:
            theme_name = row["theme_name"]
            sources = row["sources"] or ""
            source_list = [s.strip() for s in sources.split(",") if s.strip()]
            source_breakdown = json.dumps(
                {src: source_list.count(src) for src in set(source_list)}
            )

            conn.execute(
                """INSERT INTO theme_snapshots
                       (snapshot_date, theme_name, stock_count, total_market_cap,
                        avg_confidence, avg_freshness, news_mention_count, source_breakdown)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(snapshot_date, theme_name) DO UPDATE SET
                       stock_count=excluded.stock_count,
                       total_market_cap=excluded.total_market_cap,
                       avg_confidence=excluded.avg_confidence,
                       avg_freshness=excluded.avg_freshness,
                       news_mention_count=excluded.news_mention_count,
                       source_breakdown=excluded.source_breakdown""",
                (
                    snap_date, theme_name, row["stock_count"],
                    row["total_market_cap"], row["avg_confidence"],
                    freshness_map.get(theme_name),
                    news_map.get(theme_name, 0),
                    source_breakdown,
                ),
            )
            theme_count += 1

        stock_rows = conn.execute(
            """SELECT st.ticker, t.name AS theme_name, st.confidence, st.source
               FROM stock_themes st
               JOIN themes t ON t.id = st.theme_id"""
        ).fetchall()

        for row in stock_rows:
            try:
                conn.execute(
                    """INSERT INTO theme_stock_snapshots
                           (snapshot_date, theme_name, ticker, confidence, source)
                       VALUES (?, ?, ?, ?, ?)""",
                    (snap_date, row["theme_name"], row["ticker"],
                     row["confidence"], row["source"]),
                )
                pair_count += 1
            except sqlite3.IntegrityError:
                pass

    conn.close()
    return {"snapshot_date": snap_date, "themes": theme_count, "stock_theme_pairs": pair_count}
