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
from themes_api.services.regime import REGIME_COLORS, get_regime, get_regime_history
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

    regime = get_regime(conn, theme_name)
    conn.close()

    return {
        "theme_name": theme_name,
        "stock_count": len(stocks),
        "total_market_cap": total_mkt_cap,
        "avg_confidence": round(avg_conf, 4),
        "regime": regime.regime_label,
        "regime_score": regime.regime_score,
        "regime_direction": regime.regime_direction,
        "watch_status": regime.watch_status,
        "regime_color": regime.color,
        "stocks": stocks,
    }


@router.get("/{theme_name}/regime")
def theme_regime(theme_name: str):
    conn = init_db(config.DB_PATH)
    regime = get_regime(conn, theme_name)
    conn.close()

    return {
        "theme_name": theme_name,
        "regime_score": regime.regime_score,
        "regime_label": regime.regime_label,
        "regime_direction": regime.regime_direction,
        "watch_status": regime.watch_status,
        "color": regime.color,
        "signals": regime.signals,
    }


@router.get("/{theme_name}/regime-history")
def regime_history(theme_name: str, days: int = Query(90, ge=7, le=365)):
    """Regime score time series for charting."""
    conn = init_db(config.DB_PATH)
    try:
        return get_regime_history(conn, theme_name, days)
    finally:
        conn.close()


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


@router.get("/{theme_name}/technicals")
def theme_technicals(theme_name: str):
    """Theme-level + per-stock technicals."""
    conn = init_db(config.DB_PATH)
    try:
        tech = conn.execute(
            """SELECT avg_ma20_distance_pct, pct_above_ma20, avg_volume_trend,
                      avg_analyst_upside_pct, avg_positive_surprises, snapshot_date
               FROM theme_technicals
               WHERE theme_name = ?
               ORDER BY snapshot_date DESC LIMIT 1""",
            (theme_name,),
        ).fetchone()

        stock_rows = conn.execute(
            """SELECT st_tech.ticker, st_tech.close_price, st_tech.ma20_distance_pct,
                      st_tech.volume_trend, st_tech.analyst_target, st_tech.analyst_upside_pct,
                      st_tech.positive_surprises, st_tech.gross_margin, st_tech.return_on_equity,
                      st_tech.trailing_pe, st_tech.short_pct_of_float,
                      st_tech.insider_buy_count, st_tech.insider_sell_count
               FROM stock_technicals st_tech
               JOIN stock_themes sth ON sth.ticker = st_tech.ticker
               JOIN themes t ON t.id = sth.theme_id
               WHERE t.name = ?
               ORDER BY st_tech.close_price DESC""",
            (theme_name,),
        ).fetchall()

        return {
            "theme_name": theme_name,
            "snapshot_date": tech["snapshot_date"] if tech else None,
            "avg_ma20_distance_pct": tech["avg_ma20_distance_pct"] if tech else None,
            "pct_above_ma20": tech["pct_above_ma20"] if tech else None,
            "avg_volume_trend": tech["avg_volume_trend"] if tech else None,
            "avg_analyst_upside_pct": tech["avg_analyst_upside_pct"] if tech else None,
            "avg_positive_surprises": tech["avg_positive_surprises"] if tech else None,
            "stocks": [dict(r) for r in stock_rows],
        }
    finally:
        conn.close()


@router.get("/{theme_name}/history")
def theme_history(theme_name: str, days: int = Query(90, ge=7, le=365)):
    conn = init_db(config.DB_PATH)
    rows = conn.execute(
        """SELECT ts.snapshot_date, ts.stock_count, ts.total_market_cap,
                  ts.avg_confidence, ts.news_mention_count,
                  rs.regime_score
           FROM theme_snapshots ts
           LEFT JOIN regime_scores rs
             ON rs.theme_name = ts.theme_name AND rs.snapshot_date = ts.snapshot_date
           WHERE ts.theme_name = ? AND ts.snapshot_date >= date('now', ?)
           ORDER BY ts.snapshot_date""",
        (theme_name, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
