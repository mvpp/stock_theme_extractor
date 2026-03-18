"""Discover endpoint — unified search with FTS5 + open theme bridging."""

from __future__ import annotations

from fastapi import APIRouter, Query

from themes_api import config
from themes_api.db import (
    get_conn, populate_fts, search_fts, search_open_themes,
    get_theme_distribution,
)

router = APIRouter()


@router.get("/discover")
def discover(
    q: str = Query(..., min_length=1),
    sort_by: str = Query("confidence", pattern="^(confidence|freshness|distinctiveness|market_cap)$"),
):
    """Unified search across canonical themes, open themes, and stocks."""
    conn = get_conn()
    try:
        # Ensure FTS index is populated
        fts_count = conn.execute(
            "SELECT COUNT(*) FROM theme_fts"
        ).fetchone()[0]
        if fts_count == 0:
            populate_fts(conn)

        # 1. FTS5 search on canonical themes
        canonical = search_fts(conn, q)
        # Enrich with stock counts
        dist = {d["name"]: d for d in get_theme_distribution(conn)}
        canonical_results = []
        for c in canonical:
            info = dist.get(c["name"], {})
            canonical_results.append({
                "name": c["name"],
                "category": c["category"],
                "description": c["description"],
                "stock_count": info.get("stock_count", 0),
                "avg_confidence": info.get("avg_confidence", 0),
            })

        # 2. Open theme text search (semantic bridging)
        open_results_raw = search_open_themes(conn, q)
        # Aggregate by theme_text
        open_agg: dict[str, dict] = {}
        for r in open_results_raw:
            text = r["theme_text"]
            if text not in open_agg:
                open_agg[text] = {
                    "theme_text": text,
                    "stock_count": 0,
                    "avg_confidence": 0,
                    "total_confidence": 0,
                    "tickers": [],
                    "mapped_canonical": r.get("mapped_canonical"),
                }
            open_agg[text]["stock_count"] += 1
            open_agg[text]["total_confidence"] += r["confidence"]
            open_agg[text]["tickers"].append(r["ticker"])
        open_results = []
        for v in open_agg.values():
            v["avg_confidence"] = round(
                v["total_confidence"] / v["stock_count"], 3
            ) if v["stock_count"] else 0
            del v["total_confidence"]
            v["tickers"] = v["tickers"][:10]  # Cap displayed tickers
            open_results.append(v)

        # 3. Stock search
        stock_rows = conn.execute(
            """SELECT ticker, name, market_cap FROM stocks
               WHERE ticker LIKE ? OR name LIKE ?
               ORDER BY market_cap DESC NULLS LAST LIMIT 20""",
            (f"%{q.upper()}%", f"%{q}%"),
        ).fetchall()
        stock_results = [dict(r) for r in stock_rows]

        # Sort open results
        sort_key = {
            "confidence": lambda x: x.get("avg_confidence", 0),
            "market_cap": lambda x: x.get("stock_count", 0),
            "distinctiveness": lambda x: x.get("stock_count", 0),
            "freshness": lambda x: x.get("stock_count", 0),
        }.get(sort_by, lambda x: x.get("avg_confidence", 0))
        open_results.sort(key=sort_key, reverse=True)

        return {
            "query": q,
            "canonical": canonical_results[:20],
            "open": open_results[:20],
            "stocks": stock_results,
        }
    finally:
        conn.close()
