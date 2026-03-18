"""Narrative & 13F investor activity endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from themes_api.db import (
    get_conn, get_narrative_themes, get_narrative_trend,
    get_narrative_heatmap, get_investor_activity,
    get_investor_holdings_for_stock, search_open_themes,
)

router = APIRouter()


@router.get("/narratives")
def list_narratives(min_confidence: float = Query(0.3)):
    """All narrative themes, aggregated by theme_text."""
    conn = get_conn()
    try:
        return get_narrative_themes(conn, min_confidence)
    finally:
        conn.close()


@router.get("/narratives/trends")
def narrative_trends(days: int = Query(30, ge=7, le=365)):
    """Narrative trend data for heating/cooling analysis."""
    conn = get_conn()
    try:
        return get_narrative_trend(conn, days)
    finally:
        conn.close()


@router.get("/narratives/heatmap")
def narrative_heatmap():
    """Treemap data: categories → narrative themes → stock counts."""
    conn = get_conn()
    try:
        raw = get_narrative_heatmap(conn)
        # Group into category → children structure for treemap
        categories: dict[str, dict] = {}
        for r in raw:
            cat = r["category"] or "Uncategorized"
            if cat not in categories:
                categories[cat] = {"name": cat, "children": [], "total_stocks": 0}
            categories[cat]["children"].append({
                "name": r["theme_text"],
                "stock_count": r["stock_count"],
                "avg_confidence": round(r["avg_confidence"], 3),
                "avg_freshness": round(r["avg_freshness"] or 0, 3),
            })
            categories[cat]["total_stocks"] += r["stock_count"]
        return sorted(categories.values(), key=lambda x: x["total_stocks"], reverse=True)
    finally:
        conn.close()


@router.get("/narratives/{text}/stocks")
def narrative_stocks(text: str):
    """Stocks tagged with a specific narrative."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT s.ticker, s.name, s.market_cap, ot.confidence,
                      ot.distinctiveness, ot.freshness
               FROM open_themes ot
               JOIN stocks s ON s.ticker = ot.ticker
               WHERE ot.source = 'narrative' AND ot.theme_text = ?
               ORDER BY ot.confidence DESC""",
            (text,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/investor-activity")
def investor_activity(limit: int = Query(50, ge=1, le=200)):
    """Recent 13F activity across all stocks."""
    conn = get_conn()
    try:
        return get_investor_activity(conn, limit)
    finally:
        conn.close()


@router.get("/investor-activity/{ticker}")
def investor_activity_for_stock(ticker: str):
    """13F holdings for a specific stock."""
    conn = get_conn()
    try:
        return get_investor_holdings_for_stock(conn, ticker)
    finally:
        conn.close()
