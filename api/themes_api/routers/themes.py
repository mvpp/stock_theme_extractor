"""Theme API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from themes_api import config
from themes_api.db import (
    init_db, get_stocks_for_theme, get_open_themes_for_canonical,
    get_theme_stock_changes, get_source_breakdown_for_theme,
    get_emerging_ranked,
)
from themes_api.services.ranking import get_top_themes
from themes_api.services.regime import REGIME_COLORS, compute_signals, classify_regime
from themes_api.services.drift import compute_drift
from themes_api.services.tradeability import compute_tradeability

router = APIRouter()


@router.get("/top")
def top_themes(
    sort_by: str = Query("stock_count", pattern="^(stock_count|volume|momentum)$"),
    limit: int = Query(10, ge=1, le=100),
):
    return get_top_themes(config.DB_PATH, sort_by=sort_by, limit=limit)


@router.get("/emerging")
def emerging_themes(limit: int = Query(20, ge=1, le=100)):
    """High-quality emerging open themes ranked by composite quality score."""
    conn = init_db(config.DB_PATH)
    try:
        return get_emerging_ranked(conn, limit=limit)
    finally:
        conn.close()


@router.get("/{theme_name}")
def theme_detail(theme_name: str):
    conn = init_db(config.DB_PATH)

    stocks = get_stocks_for_theme(conn, theme_name)
    total_mkt_cap = sum(s.get("market_cap") or 0 for s in stocks)
    avg_conf = sum(s["confidence"] for s in stocks) / len(stocks) if stocks else 0

    signals = compute_signals(conn, theme_name)
    regime = classify_regime(signals)
    conn.close()

    return {
        "theme_name": theme_name,
        "stock_count": len(stocks),
        "total_market_cap": total_mkt_cap,
        "avg_confidence": round(avg_conf, 4),
        "regime": regime,
        "regime_color": REGIME_COLORS.get(regime, "#6b7280"),
        "stocks": stocks,
    }


@router.get("/{theme_name}/regime")
def theme_regime(theme_name: str):
    conn = init_db(config.DB_PATH)
    signals = compute_signals(conn, theme_name)
    regime = classify_regime(signals)
    conn.close()

    return {
        "theme_name": theme_name,
        "regime": regime,
        "color": REGIME_COLORS.get(regime, "#6b7280"),
        "signals": {
            "stock_count": signals.stock_count,
            "stock_count_velocity": round(signals.stock_count_velocity, 4),
            "confidence_trend": round(signals.confidence_trend, 6),
            "news_trend": signals.news_trend,
            "news_density": signals.news_density,
            "source_diversity": signals.source_diversity,
            "days_since_first_seen": signals.days_since_first_seen,
            "avg_confidence": round(signals.avg_confidence, 4),
        },
    }


@router.get("/{theme_name}/drift")
def theme_drift(theme_name: str, days: int = Query(90, ge=7, le=365)):
    return compute_drift(config.DB_PATH, theme_name, days)


@router.get("/{theme_name}/open-variants")
def open_variants(theme_name: str):
    """Open themes that map to this canonical theme."""
    conn = init_db(config.DB_PATH)
    try:
        return get_open_themes_for_canonical(conn, theme_name)
    finally:
        conn.close()


@router.get("/{theme_name}/stock-changes")
def stock_changes(theme_name: str, days: int = Query(30, ge=7, le=365)):
    """Stocks added/removed from a theme over the given period."""
    conn = init_db(config.DB_PATH)
    try:
        return get_theme_stock_changes(conn, theme_name, days)
    finally:
        conn.close()


@router.get("/{theme_name}/tradeability")
def tradeability(theme_name: str):
    """Composite tradeability score with 6 components."""
    conn = init_db(config.DB_PATH)
    try:
        return compute_tradeability(conn, theme_name)
    finally:
        conn.close()


@router.get("/{theme_name}/history")
def theme_history(theme_name: str, days: int = Query(90, ge=7, le=365)):
    conn = init_db(config.DB_PATH)
    rows = conn.execute(
        """SELECT snapshot_date, stock_count, total_market_cap,
                  avg_confidence, news_mention_count
           FROM theme_snapshots
           WHERE theme_name = ? AND snapshot_date >= date('now', ?)
           ORDER BY snapshot_date""",
        (theme_name, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
