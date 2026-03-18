"""Stock screener service — thin wrapper around db.screener_query."""

from __future__ import annotations

import sqlite3

from themes_api.db import screener_query, get_themes_for_stock, get_filtered_open_themes


def run_screener(conn: sqlite3.Connection, filters: dict) -> list[dict]:
    """Run a multi-filter screener and enrich results with theme info."""
    stocks = screener_query(conn, filters)

    # Optionally enrich with top themes per stock
    for stock in stocks:
        themes = get_themes_for_stock(conn, stock["ticker"], min_confidence=0.3)
        stock["themes"] = [
            {"name": t["name"], "confidence": t["confidence"], "source": t["source"]}
            for t in themes[:5]
        ]

    return stocks
