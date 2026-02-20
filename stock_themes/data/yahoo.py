"""Yahoo Finance data provider."""

from __future__ import annotations

import logging
import time
from io import StringIO

import requests
import yfinance as yf
from yfinance import EquityQuery

from stock_themes.config import YAHOO_RATE_LIMIT_DELAY, FAKE_USER_AGENT
from stock_themes.exceptions import ProviderError, TickerNotFoundError
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)


class YahooFinanceProvider:
    name = "yahoo_finance"

    def is_available(self) -> bool:
        return True

    def fetch(self, ticker: str) -> CompanyProfile:
        """Fetch company profile from Yahoo Finance."""
        try:
            stock = yf.Ticker(ticker.upper())
            info = stock.info
        except Exception as e:
            raise ProviderError(f"Yahoo Finance request failed for {ticker}: {e}")

        if not info or not info.get("shortName"):
            raise TickerNotFoundError(f"Ticker '{ticker}' not found on Yahoo Finance")

        return CompanyProfile(
            ticker=ticker.upper(),
            name=info.get("shortName", ""),
            sector=info.get("sector"),
            industry=info.get("industry"),
            market_cap=info.get("marketCap"),
            exchange=info.get("exchange"),
            employees=info.get("fullTimeEmployees"),
            website=info.get("website"),
            business_summary=info.get("longBusinessSummary"),
            data_sources=["yahoo_finance"],
        )


def discover_us_tickers() -> list[dict]:
    """Discover all US-listed stock tickers with basic info.

    Returns list of dicts with keys: ticker, name, market_cap, exchange.

    Fallback chain:
      1. yf.screen() with EquityQuery (all US equities, paginated)
      2. Wikipedia S&P 500 constituent list
      3. Local stock_symbols.csv file
    """
    logger.info("Discovering US stock tickers via yfinance screener...")
    all_tickers = []

    try:
        query = EquityQuery('eq', ['region', 'us'])
        offset = 0
        batch_size = 250

        while True:
            response = yf.screen(
                query,
                sortField='intradaymarketcap',
                sortAsc=False,
                size=batch_size,
                count=batch_size,  # must also set count to prevent yfinance default of 25
                offset=offset,
            )
            quotes = response.get("quotes", [])
            if not quotes:
                break

            for q in quotes:
                sym = q.get("symbol", "")
                # Keep only short tickers (≤4 chars) — filters out OTC/foreign
                # tickers like ASMLF, TCEHY, TCTZF that are typically duplicates
                if sym and len(sym) <= 4:
                    all_tickers.append({
                        "ticker": sym,
                        "name": q.get("shortName", ""),
                        "market_cap": q.get("marketCap"),
                        "exchange": q.get("exchange", ""),
                    })

            total = response.get("total", response.get("count", None))
            logger.info(
                f"Screener page {offset // batch_size + 1}: "
                f"got {len(quotes)} quotes, {len(all_tickers)} total so far"
                + (f" (server total: {total})" if total else "")
            )

            offset += batch_size
            time.sleep(YAHOO_RATE_LIMIT_DELAY)

            # Stop if we got fewer results than requested (last page)
            if len(quotes) < batch_size:
                break
            # Stop if server tells us total and we've fetched them all
            if total and offset >= total:
                break

        logger.info(f"Discovered {len(all_tickers)} US tickers via screener")
    except Exception as e:
        logger.warning(f"Screener approach failed: {e}, trying fallback...")

    if not all_tickers:
        all_tickers = _fallback_ticker_discovery()
    if not all_tickers:
        all_tickers = _csv_ticker_discovery()

    return all_tickers


def _fallback_ticker_discovery() -> list[dict]:
    """Fallback: scrape S&P 500 constituents from Wikipedia."""
    logger.info("Using fallback ticker discovery (Wikipedia S&P 500)...")
    try:
        import pandas as pd

        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        resp = requests.get(
            url, headers={"User-Agent": FAKE_USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        sp500 = tables[0]

        tickers = []
        for _, row in sp500.iterrows():
            tickers.append({
                "ticker": row["Symbol"].replace(".", "-"),
                "name": row.get("Security", ""),
                "market_cap": None,
                "exchange": "",
            })

        logger.info(f"Fallback discovered {len(tickers)} tickers")
        return tickers
    except Exception as e:
        logger.warning(f"S&P 500 fallback failed: {e}")
        return []


def _csv_ticker_discovery() -> list[dict]:
    """Ultimate fallback: load tickers from local stock_symbols.csv.

    Expected CSV column: 'symbol' (required).
    Optional columns: 'name', 'market_cap', 'exchange'.
    """
    from stock_themes.config import PROJECT_ROOT

    csv_path = PROJECT_ROOT / "stock_symbols.csv"
    if not csv_path.exists():
        logger.warning(f"No CSV fallback at {csv_path}")
        return []

    try:
        import pandas as pd

        df = pd.read_csv(csv_path)
        col = "symbol" if "symbol" in df.columns else df.columns[0]
        tickers = []
        for _, row in df.iterrows():
            sym = str(row[col]).strip().upper()
            if sym and sym != "NAN":
                tickers.append({
                    "ticker": sym,
                    "name": str(row.get("name", "")) if "name" in df.columns else "",
                    "market_cap": row.get("market_cap") if "market_cap" in df.columns else None,
                    "exchange": str(row.get("exchange", "")) if "exchange" in df.columns else "",
                })

        logger.info(f"CSV fallback loaded {len(tickers)} tickers from {csv_path}")
        return tickers
    except Exception as e:
        logger.warning(f"CSV fallback failed: {e}")
        return []
