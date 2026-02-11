"""StockTwits data provider with daily collection and monthly aggregation."""

from __future__ import annotations

import logging
import sys
from datetime import datetime

import requests

from stock_themes.exceptions import ProviderError
from stock_themes.models import CompanyProfile, SocialMessage
from stock_themes.db.store import ThemeStore

logger = logging.getLogger(__name__)

STOCKTWITS_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"


class StockTwitsProvider:
    name = "stocktwits"

    def is_available(self) -> bool:
        return True

    def fetch_messages(self, ticker: str) -> list[SocialMessage]:
        """Fetch latest 30 messages for a ticker from StockTwits."""
        url = STOCKTWITS_API.format(ticker=ticker.upper())
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"StockTwits API failed for {ticker}: {e}")

        if data.get("response", {}).get("status") != 200:
            return []

        messages = []
        for msg in data.get("messages", []):
            sentiment = None
            entities = msg.get("entities", {})
            if entities and entities.get("sentiment"):
                sentiment = entities["sentiment"].get("basic")

            created_str = msg.get("created_at")
            created_at = None
            if created_str:
                try:
                    created_at = datetime.strptime(
                        created_str, "%Y-%m-%dT%H:%M:%SZ"
                    )
                except ValueError:
                    pass

            messages.append(SocialMessage(
                ticker=ticker.upper(),
                source="stocktwits",
                message_id=str(msg.get("id", "")),
                body=msg.get("body", ""),
                sentiment=sentiment,
                created_at=created_at,
            ))

        logger.info(f"{ticker}: fetched {len(messages)} StockTwits messages")
        return messages

    def fetch(self, ticker: str, db_path: str | None = None) -> CompanyProfile:
        """Fetch and optionally store messages. Return as CompanyProfile."""
        messages = self.fetch_messages(ticker)

        if db_path and messages:
            store = ThemeStore(db_path)
            inserted = store.store_social_messages(messages)
            store.close()
            logger.info(f"{ticker}: stored {inserted} new StockTwits messages")

        # Build social text from non-bearish messages
        positive_msgs = [
            m.body for m in messages
            if m.sentiment != "Bearish"
        ]
        social_text = " ".join(positive_msgs) if positive_msgs else None

        # Extract sentiment summary
        sentiment_counts = {"bullish": 0, "bearish": 0, "neutral": 0}
        for m in messages:
            if m.sentiment == "Bullish":
                sentiment_counts["bullish"] += 1
            elif m.sentiment == "Bearish":
                sentiment_counts["bearish"] += 1
            else:
                sentiment_counts["neutral"] += 1

        return CompanyProfile(
            ticker=ticker.upper(),
            name="",
            social_text=social_text,
            social_sentiment=sentiment_counts if messages else None,
            data_sources=["stocktwits"],
        )


def collect_daily(db_path: str, tickers: list[str]) -> dict[str, int]:
    """Daily collection job: fetch StockTwits messages for all tickers.

    Returns dict of {ticker: messages_inserted}.
    """
    from tqdm import tqdm

    provider = StockTwitsProvider()
    store = ThemeStore(db_path)
    results = {}

    for ticker in tqdm(tickers, desc="Collecting StockTwits"):
        try:
            messages = provider.fetch_messages(ticker)
            if messages:
                inserted = store.store_social_messages(messages)
                results[ticker] = inserted
        except Exception as e:
            logger.warning(f"StockTwits collection failed for {ticker}: {e}")
            results[ticker] = 0

    store.close()
    total = sum(results.values())
    logger.info(f"Daily collection complete: {total} new messages across {len(results)} tickers")
    return results


def get_monthly_social_text(db_path: str, ticker: str) -> str | None:
    """Get aggregated social text for a ticker from past 30 days.

    Filters for neutral + positive sentiment only.
    """
    store = ThemeStore(db_path)
    text = store.get_social_text(
        ticker, days=30, sentiment_filter=["Bullish", None]
    )
    store.close()
    return text if text.strip() else None


# CLI entry point for daily cron job
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m stock_themes.data.social <db_path> [ticker1 ticker2 ...]")
        sys.exit(1)

    db_path = sys.argv[1]
    if len(sys.argv) > 2:
        tickers = [t.upper() for t in sys.argv[2:]]
    else:
        # Load all tickers from the database
        store = ThemeStore(db_path)
        tickers = store.get_all_tickers()
        store.close()

    if not tickers:
        print("No tickers found. Provide tickers as arguments or populate the database first.")
        sys.exit(1)

    results = collect_daily(db_path, tickers)
    print(f"Collected {sum(results.values())} new messages for {len(results)} tickers")
