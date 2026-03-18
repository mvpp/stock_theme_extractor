"""Stock API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from themes_api import config
from themes_api.db import (
    get_conn, get_stock, get_theme_distribution,
    get_all_themes, find_stocks, get_investor_holdings_for_stock,
)

router = APIRouter()


@router.get("")
def list_stocks(theme: str | None = Query(None)):
    """List stocks, optionally filtered by theme."""
    conn = get_conn()
    try:
        if theme:
            return find_stocks(conn, theme)
        return get_theme_distribution(conn)
    finally:
        conn.close()


@router.get("/{ticker}")
def stock_detail(ticker: str):
    conn = get_conn()
    try:
        stock = get_stock(conn, ticker.upper())
        if not stock:
            return {"error": f"Stock {ticker} not found"}

        themes = get_all_themes(conn, ticker.upper())
        holdings = get_investor_holdings_for_stock(conn, ticker.upper())

        return {
            **stock,
            "themes": themes,
            "investor_holdings": holdings,
        }
    finally:
        conn.close()
