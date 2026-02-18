"""Batch processor: build the full stock themes database."""

from __future__ import annotations

import logging
import time

from tqdm import tqdm

from stock_themes.config import (
    LLM_MARKET_CAP_THRESHOLD,
    LLM_DELAY_SECONDS,
    BATCH_SIZE,
)
from stock_themes.data.pipeline import DataPipeline
from stock_themes.extraction.ensemble import EnsembleExtractor
from stock_themes.db.store import ThemeStore

logger = logging.getLogger(__name__)


def run_batch(
    db_path: str = "stock_themes.db",
    llm_market_cap_threshold: float = LLM_MARKET_CAP_THRESHOLD,
    max_themes_per_stock: int = 10,
    skip_existing: bool = True,
    tickers: list[str] | None = None,
) -> dict:
    """Process all US stocks and populate the database.

    Args:
        db_path: Path to SQLite database.
        llm_market_cap_threshold: Market cap threshold for LLM usage.
        max_themes_per_stock: Max themes per stock.
        skip_existing: Skip tickers already processed.
        tickers: If provided, only process these tickers. Otherwise discover all US tickers.

    Returns:
        Dict with statistics.
    """
    store = ThemeStore(db_path)
    stats = {"processed": 0, "skipped": 0, "failed": 0, "total": 0}

    # Discover tickers
    if tickers is None:
        from stock_themes.data.yahoo import discover_us_tickers
        ticker_data = discover_us_tickers()
        tickers_to_process = [t["ticker"] for t in ticker_data if t["ticker"]]
    else:
        tickers_to_process = [t.upper() for t in tickers]

    stats["total"] = len(tickers_to_process)
    logger.info(f"Processing {len(tickers_to_process)} tickers")

    # Filter out already-processed tickers
    if skip_existing:
        existing = set(store.get_all_tickers())
        original_count = len(tickers_to_process)
        tickers_to_process = [t for t in tickers_to_process if t not in existing]
        stats["skipped"] = original_count - len(tickers_to_process)
        logger.info(f"Skipping {stats['skipped']} already-processed tickers")

    # Set up pipeline and extractor (reuse across tickers)
    pipeline = DataPipeline()
    extractor = EnsembleExtractor(use_llm=True, max_themes=max_themes_per_stock)

    # Process tickers
    for ticker in tqdm(tickers_to_process, desc="Processing stocks"):
        try:
            _process_single(
                ticker=ticker,
                pipeline=pipeline,
                extractor=extractor,
                store=store,
                db_path=db_path,
                llm_market_cap_threshold=llm_market_cap_threshold,
            )
            stats["processed"] += 1
        except Exception as e:
            logger.warning(f"Failed to process {ticker}: {e}")
            stats["failed"] += 1

    store.close()
    logger.info(
        f"Batch complete: {stats['processed']} processed, "
        f"{stats['failed']} failed, {stats['skipped']} skipped"
    )
    return stats


def _process_single(
    ticker: str,
    pipeline: DataPipeline,
    extractor: EnsembleExtractor,
    store: ThemeStore,
    db_path: str,
    llm_market_cap_threshold: float = LLM_MARKET_CAP_THRESHOLD,
) -> None:
    """Process a single ticker: fetch data, extract themes, save to DB."""

    # Fetch all data (two-pass: core providers then enrichment with company name)
    # db_path lets StockTwits read accumulated monthly messages from the DB
    profile = pipeline.fetch(ticker, db_path=db_path)

    # Extract themes
    result = extractor.extract(profile)

    # Save to database
    store.save_theme_result(result)

    # Rate limit for LLM calls
    market_cap = profile.market_cap or 0
    if market_cap >= llm_market_cap_threshold:
        time.sleep(LLM_DELAY_SECONDS)
