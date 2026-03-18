#!/usr/bin/env python3
"""Daily price data pipeline — fetches OHLCV, computes technicals, aggregates per theme.

Run after market close:
    python scripts/refresh_prices.py --db stock_themes.db
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yfinance as yf

# Allow running as script from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from themes_api.db import init_db  # noqa: E402

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 0.5  # seconds between per-ticker yf.Ticker() calls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slope(values: list[float]) -> float:
    """Simple linear regression slope."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    sum_x = sum(xs)
    sum_y = sum(values)
    sum_xy = sum(x * y for x, y in zip(xs, values))
    sum_xx = sum(x * x for x in xs)
    denom = n * sum_xx - sum_x ** 2
    return (n * sum_xy - sum_x * sum_y) / denom if denom else 0.0


def _safe_get(info: dict, key: str, default=None):
    """Get a value from yfinance info dict, returning default for None/NaN."""
    val = info.get(key, default)
    if val is None:
        return default
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return default
    return val


# ---------------------------------------------------------------------------
# Step 1: Batch OHLCV download
# ---------------------------------------------------------------------------

def fetch_ohlcv(conn: sqlite3.Connection, tickers: list[str]) -> tuple[int, int]:
    """Download 3 months of OHLCV for all tickers in one batch call."""
    if not tickers:
        return 0, 0

    logger.info("Downloading OHLCV for %d tickers...", len(tickers))
    data = yf.download(tickers, period="3mo", group_by="ticker", progress=False)

    if data.empty:
        logger.warning("yf.download returned empty DataFrame")
        return 0, len(tickers)

    today_str = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    ok, failed = 0, 0

    for ticker in tickers:
        try:
            if len(tickers) == 1:
                ticker_data = data
            else:
                ticker_data = data[ticker]

            if ticker_data.empty or ticker_data["Close"].isna().all():
                failed += 1
                continue

            rows = []
            for idx, row in ticker_data.iterrows():
                price_date = idx.strftime("%Y-%m-%d")
                close_val = row.get("Close")
                if close_val is None or (isinstance(close_val, float) and math.isnan(close_val)):
                    continue
                rows.append((
                    ticker, price_date,
                    _nan_to_none(row.get("Open")),
                    _nan_to_none(row.get("High")),
                    _nan_to_none(row.get("Low")),
                    _nan_to_none(close_val),
                    _nan_to_none_int(row.get("Volume")),
                ))

            if rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO stock_prices "
                    "(ticker, price_date, open, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                ok += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning("Failed to process OHLCV for %s: %s", ticker, e)
            failed += 1

    # Prune old data
    conn.execute("DELETE FROM stock_prices WHERE price_date < ?", (cutoff,))
    conn.commit()
    logger.info("OHLCV: %d succeeded, %d failed", ok, failed)
    return ok, failed


def _nan_to_none(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _nan_to_none_int(val) -> int | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else int(f)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Step 2: Compute per-stock technicals from price data
# ---------------------------------------------------------------------------

def compute_stock_technicals(conn: sqlite3.Connection, tickers: list[str]) -> None:
    """Compute MA20, volume trend from stock_prices for each ticker."""
    for ticker in tickers:
        rows = conn.execute(
            "SELECT price_date, close, volume FROM stock_prices "
            "WHERE ticker = ? ORDER BY price_date DESC LIMIT 60",
            (ticker,),
        ).fetchall()

        if len(rows) < 20:
            continue

        closes = [r["close"] for r in rows if r["close"] is not None]
        volumes = [r["volume"] for r in rows if r["volume"] is not None]

        if len(closes) < 20:
            continue

        latest_close = closes[0]
        ma20 = sum(closes[:20]) / 20
        ma20_dist = (latest_close - ma20) / ma20 * 100 if ma20 else 0

        vol_20d_avg = int(sum(volumes[:20]) / 20) if len(volumes) >= 20 else None
        # Volume trend: slope of last 20 days, normalized
        vol_trend = 0.0
        if len(volumes) >= 20:
            recent_vols = list(reversed(volumes[:20]))  # oldest first
            mean_vol = sum(recent_vols) / len(recent_vols)
            if mean_vol > 0:
                vol_trend = _slope(recent_vols) / mean_vol

        conn.execute(
            """INSERT OR REPLACE INTO stock_technicals
               (ticker, price_date, close_price, ma20, ma20_distance_pct,
                volume_20d_avg, volume_trend)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET
                 price_date=excluded.price_date,
                 close_price=excluded.close_price,
                 ma20=excluded.ma20,
                 ma20_distance_pct=excluded.ma20_distance_pct,
                 volume_20d_avg=excluded.volume_20d_avg,
                 volume_trend=excluded.volume_trend,
                 updated_at=CURRENT_TIMESTAMP""",
            (ticker, rows[0]["price_date"], latest_close,
             round(ma20, 4), round(ma20_dist, 4), vol_20d_avg,
             round(vol_trend, 6)),
        )

    conn.commit()


# ---------------------------------------------------------------------------
# Step 3: Fetch per-ticker info (analyst, fundamentals, earnings, insider)
# ---------------------------------------------------------------------------

def fetch_ticker_info(conn: sqlite3.Connection, tickers: list[str]) -> tuple[int, int]:
    """Fetch analyst targets, fundamentals, earnings, insider data per ticker."""
    ok, failed = 0, 0

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}

            analyst_target = _safe_get(info, "targetMeanPrice")
            close_price = _safe_get(info, "currentPrice") or _safe_get(info, "previousClose")
            analyst_upside = None
            if analyst_target and close_price and close_price > 0:
                analyst_upside = (analyst_target - close_price) / close_price * 100

            # Earnings surprises
            positive_surprises = 0
            try:
                eh = stock.earnings_history
                if eh is not None and not eh.empty:
                    for _, row in eh.tail(4).iterrows():
                        sp = row.get("surprisePercent")
                        if sp is not None and not math.isnan(sp) and sp > 0:
                            positive_surprises += 1
            except Exception:
                pass

            # Insider transactions
            insider_buy, insider_sell = 0, 0
            try:
                txns = stock.insider_transactions
                if txns is not None and not txns.empty:
                    six_months_ago = datetime.now() - timedelta(days=180)
                    for _, row in txns.iterrows():
                        start_date = row.get("Start Date") or row.get("startDate")
                        if start_date is not None:
                            try:
                                if hasattr(start_date, "to_pydatetime"):
                                    txn_date = start_date.to_pydatetime()
                                else:
                                    txn_date = datetime.fromisoformat(str(start_date))
                                if txn_date < six_months_ago:
                                    continue
                            except Exception:
                                pass
                        text = str(row.get("Text", "") or row.get("Transaction", "")).lower()
                        if "purchase" in text or "buy" in text:
                            insider_buy += 1
                        elif "sale" in text or "sell" in text:
                            insider_sell += 1
            except Exception:
                pass

            conn.execute(
                """UPDATE stock_technicals SET
                     analyst_target = ?,
                     analyst_upside_pct = ?,
                     analyst_count = ?,
                     recommendation_mean = ?,
                     positive_surprises = ?,
                     gross_margin = ?,
                     operating_margin = ?,
                     profit_margin = ?,
                     return_on_equity = ?,
                     return_on_assets = ?,
                     debt_to_equity = ?,
                     current_ratio = ?,
                     free_cashflow = ?,
                     operating_cashflow = ?,
                     trailing_pe = ?,
                     forward_pe = ?,
                     peg_ratio = ?,
                     beta = ?,
                     dividend_yield = ?,
                     earnings_growth = ?,
                     revenue_growth = ?,
                     trailing_eps = ?,
                     forward_eps = ?,
                     held_pct_institutions = ?,
                     short_pct_of_float = ?,
                     short_ratio = ?,
                     insider_buy_count = ?,
                     insider_sell_count = ?,
                     updated_at = CURRENT_TIMESTAMP
                   WHERE ticker = ?""",
                (
                    _safe_get(info, "targetMeanPrice"),
                    round(analyst_upside, 4) if analyst_upside is not None else None,
                    _safe_get(info, "numberOfAnalystOpinions"),
                    _safe_get(info, "recommendationMean"),
                    positive_surprises,
                    _safe_get(info, "grossMargins"),
                    _safe_get(info, "operatingMargins"),
                    _safe_get(info, "profitMargins"),
                    _safe_get(info, "returnOnEquity"),
                    _safe_get(info, "returnOnAssets"),
                    _safe_get(info, "debtToEquity"),
                    _safe_get(info, "currentRatio"),
                    _safe_get(info, "freeCashflow"),
                    _safe_get(info, "operatingCashflow"),
                    _safe_get(info, "trailingPE"),
                    _safe_get(info, "forwardPE"),
                    _safe_get(info, "pegRatio"),
                    _safe_get(info, "beta"),
                    _safe_get(info, "dividendYield"),
                    _safe_get(info, "earningsGrowth"),
                    _safe_get(info, "revenueGrowth"),
                    _safe_get(info, "trailingEps"),
                    _safe_get(info, "forwardEps"),
                    _safe_get(info, "heldPercentInstitutions"),
                    _safe_get(info, "shortPercentOfFloat"),
                    _safe_get(info, "shortRatio"),
                    insider_buy,
                    insider_sell,
                    ticker,
                ),
            )
            ok += 1
        except Exception as e:
            logger.warning("Failed to fetch info for %s: %s", ticker, e)
            failed += 1

        time.sleep(RATE_LIMIT_DELAY)

    conn.commit()
    logger.info("Ticker info: %d succeeded, %d failed", ok, failed)
    return ok, failed


# ---------------------------------------------------------------------------
# Step 4: Aggregate theme-level technicals
# ---------------------------------------------------------------------------

def aggregate_theme_technicals(conn: sqlite3.Connection) -> None:
    """Market-cap-weighted average of per-stock technicals for each theme."""
    today_str = date.today().isoformat()

    rows = conn.execute(
        """SELECT t.name AS theme_name,
                  s.market_cap,
                  st_tech.ma20_distance_pct,
                  st_tech.volume_trend,
                  st_tech.analyst_upside_pct,
                  st_tech.positive_surprises
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           JOIN stocks s ON s.ticker = st.ticker
           LEFT JOIN stock_technicals st_tech ON st_tech.ticker = s.ticker
           WHERE st_tech.ticker IS NOT NULL"""
    ).fetchall()

    themes: dict[str, list] = {}
    for r in rows:
        name = r["theme_name"]
        if name not in themes:
            themes[name] = []
        themes[name].append(dict(r))

    for theme_name, stocks in themes.items():
        total_cap = sum(s["market_cap"] or 1 for s in stocks)
        if total_cap <= 0:
            total_cap = len(stocks)

        avg_ma20 = 0.0
        above_ma20 = 0
        avg_vol = 0.0
        avg_upside = 0.0
        avg_surprises = 0.0

        for s in stocks:
            w = (s["market_cap"] or 1) / total_cap
            if s["ma20_distance_pct"] is not None:
                avg_ma20 += w * s["ma20_distance_pct"]
                if s["ma20_distance_pct"] > 0:
                    above_ma20 += 1
            if s["volume_trend"] is not None:
                avg_vol += w * s["volume_trend"]
            if s["analyst_upside_pct"] is not None:
                avg_upside += w * s["analyst_upside_pct"]
            if s["positive_surprises"] is not None:
                avg_surprises += w * s["positive_surprises"]

        pct_above = above_ma20 / len(stocks) if stocks else 0

        conn.execute(
            "INSERT OR REPLACE INTO theme_technicals "
            "(theme_name, snapshot_date, avg_ma20_distance_pct, pct_above_ma20, "
            "avg_volume_trend, avg_analyst_upside_pct, avg_positive_surprises) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (theme_name, today_str, round(avg_ma20, 4), round(pct_above, 4),
             round(avg_vol, 6), round(avg_upside, 4), round(avg_surprises, 4)),
        )

    conn.commit()
    logger.info("Aggregated technicals for %d themes", len(themes))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Daily price data pipeline")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    conn = init_db(args.db)
    tickers = [r["ticker"] for r in conn.execute("SELECT ticker FROM stocks ORDER BY ticker").fetchall()]
    logger.info("Processing %d tickers", len(tickers))

    today_str = date.today().isoformat()
    status = "success"
    error_msg = None
    total_ok, total_failed = 0, 0

    try:
        # Step 1: Batch OHLCV
        ok, failed = fetch_ohlcv(conn, tickers)
        total_ok += ok
        total_failed += failed

        # Step 2: Compute MA20, volume trend from price data
        compute_stock_technicals(conn, tickers)

        # Step 3: Per-ticker fundamentals
        ok2, failed2 = fetch_ticker_info(conn, tickers)
        total_ok = min(total_ok, ok2)
        total_failed = max(total_failed, failed2)

        # Step 4: Aggregate per theme
        aggregate_theme_technicals(conn)

        if total_failed > len(tickers) * 0.5:
            status = "partial"
    except Exception as e:
        status = "failed"
        error_msg = str(e)
        logger.error("Pipeline failed: %s", e)

    # Record pipeline run
    conn.execute(
        "INSERT OR REPLACE INTO pipeline_runs "
        "(pipeline_name, run_date, status, tickers_processed, tickers_failed, "
        "error_message, completed_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("price_pipeline", today_str, status, total_ok, total_failed, error_msg),
    )
    conn.commit()
    conn.close()
    logger.info("Pipeline complete: status=%s", status)


if __name__ == "__main__":
    main()
