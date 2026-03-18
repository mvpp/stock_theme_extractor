"""Unified search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query

from themes_api.db import (
    get_conn, get_theme_distribution, get_all_tickers,
    get_stock, search_open_themes,
)

router = APIRouter()


@router.get("/search")
def search(q: str = Query(..., min_length=1)):
    """Search across themes, stocks, and open themes."""
    conn = get_conn()
    try:
        query = q.strip().lower()

        all_themes = get_theme_distribution(conn)
        matching_themes = [
            t for t in all_themes
            if query in t["name"].lower()
        ]

        all_tickers = get_all_tickers(conn)
        matching_stocks = []
        for ticker in all_tickers:
            if query in ticker.lower():
                stock = get_stock(conn, ticker)
                if stock:
                    matching_stocks.append(stock)
                if len(matching_stocks) >= 20:
                    break

        if len(matching_stocks) < 20:
            open_results = search_open_themes(
                conn, q, min_confidence=0.0, min_distinctiveness=0.0,
                max_mapped_similarity=1.0,
            )
            seen = {s["ticker"] for s in matching_stocks}
            for r in open_results:
                if r["ticker"] not in seen:
                    matching_stocks.append({
                        "ticker": r["ticker"],
                        "name": r["name"],
                        "market_cap": r["market_cap"],
                        "match_reason": f"open theme: {r['theme_text']}",
                    })
                    seen.add(r["ticker"])
                if len(matching_stocks) >= 20:
                    break

        return {
            "query": q,
            "themes": matching_themes[:20],
            "stocks": matching_stocks[:20],
        }
    finally:
        conn.close()
