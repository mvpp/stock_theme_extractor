"""Yahoo Finance data provider."""

from __future__ import annotations

import logging
import time

import yfinance as yf

from stock_themes.config import YAHOO_RATE_LIMIT_DELAY
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
    """
    logger.info("Discovering US stock tickers via yfinance screener...")

    # Use yfinance screener for US exchanges
    exchanges = ["NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "BTS"]
    all_tickers = []

    for exchange in exchanges:
        try:
            screener = yf.Screener()
            # yfinance screener may not support filtering by exchange directly
            # Fall back to a well-known approach
            pass
        except Exception:
            pass

    # Fallback: use a broader approach with S&P constituents + Russell 3000
    # For a comprehensive list, we download from yfinance tickers endpoint
    try:
        # Get a broad list of US equities
        # yfinance doesn't have a built-in "all US tickers" endpoint,
        # so we use the stock screener with broad criteria
        screener = yf.Screener()
        screener.set_default_body({
            "offset": 0,
            "size": 250,
            "sortField": "intradaymarketcap",
            "sortType": "DESC",
            "quoteType": "EQUITY",
            "query": {
                "operator": "AND",
                "operands": [
                    {"operator": "EQ", "operands": ["region", "us"]},
                ],
            },
        })

        tickers_batch = []
        offset = 0
        batch_size = 250

        while True:
            screener.body["offset"] = offset
            try:
                response = screener.response
                quotes = response.get("quotes", [])
                if not quotes:
                    break

                for q in quotes:
                    tickers_batch.append({
                        "ticker": q.get("symbol", ""),
                        "name": q.get("shortName", ""),
                        "market_cap": q.get("marketCap"),
                        "exchange": q.get("exchange", ""),
                    })

                offset += batch_size
                time.sleep(YAHOO_RATE_LIMIT_DELAY)

                if len(quotes) < batch_size:
                    break
            except Exception as e:
                logger.warning(f"Screener batch at offset {offset} failed: {e}")
                break

        all_tickers = tickers_batch
        logger.info(f"Discovered {len(all_tickers)} US tickers via screener")

    except Exception as e:
        logger.warning(f"Screener approach failed: {e}, trying fallback...")
        all_tickers = _fallback_ticker_discovery()

    if not all_tickers:
        all_tickers = _fallback_ticker_discovery()

    return all_tickers


def _fallback_ticker_discovery() -> list[dict]:
    """Fallback: use known index constituents for ticker discovery."""
    import requests

    logger.info("Using fallback ticker discovery (Wikipedia S&P 500 + others)...")
    tickers = []

    # S&P 500 from Wikipedia
    try:
        import pandas as pd
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        sp500 = tables[0]
        for _, row in sp500.iterrows():
            tickers.append({
                "ticker": row["Symbol"].replace(".", "-"),
                "name": row.get("Security", ""),
                "market_cap": None,
                "exchange": "",
            })
    except Exception as e:
        logger.warning(f"S&P 500 fallback failed: {e}")

    # Add known large tickers not in S&P 500 if needed
    logger.info(f"Fallback discovered {len(tickers)} tickers")
    return tickers
