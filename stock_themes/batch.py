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
    max_tickers: int | None = None,
    refresh_after: str | None = None,
) -> dict:
    """Process all US stocks and populate the database.

    Args:
        db_path: Path to SQLite database.
        llm_market_cap_threshold: Market cap threshold for LLM usage.
        max_themes_per_stock: Max themes per stock.
        skip_existing: Skip tickers already processed.
        tickers: If provided, only process these tickers. Otherwise discover all US tickers.
        max_tickers: If set, process at most this many tickers per run. Enables
            chunked cron scheduling — each invocation picks up the next N
            unprocessed tickers automatically.
        refresh_after: ISO date string (e.g. "2025-01-01"). When set, tickers
            last updated before this date are treated as unprocessed and will be
            re-queued. Use for seasonal rebuilds. Requires skip_existing=True.

    Returns:
        Dict with statistics (processed, skipped, failed, total).
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
    print(f"Discovered {stats['total']} US stock tickers")
    logger.info(f"Processing {len(tickers_to_process)} tickers")

    # Filter out already-processed tickers (respecting refresh_after cutoff)
    if skip_existing:
        existing = set(store.get_tickers_updated_since(refresh_after))
        original_count = len(tickers_to_process)
        tickers_to_process = [t for t in tickers_to_process if t not in existing]
        stats["skipped"] = original_count - len(tickers_to_process)
        logger.info(f"Skipping {stats['skipped']} already-processed tickers")

    # Limit to N tickers for chunked cron runs
    if max_tickers is not None:
        tickers_to_process = tickers_to_process[:max_tickers]
        logger.info(
            f"max_tickers={max_tickers}: processing {len(tickers_to_process)} tickers this run"
        )

    # Set up pipeline and extractor (reuse across tickers)
    pipeline = DataPipeline()
    extractor = EnsembleExtractor(use_llm=True, max_themes=max_themes_per_stock)

    # Process tickers
    run_start = time.monotonic()
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
    elapsed = time.monotonic() - run_start
    per_ticker = elapsed / stats["processed"] if stats["processed"] else 0
    summary = (
        f"Done: {stats['processed']} processed, {stats['failed']} failed, "
        f"{stats['skipped']} skipped — {elapsed / 60:.1f} min total "
        f"({per_ticker:.1f}s/ticker avg)"
    )
    print(summary)
    logger.info(summary)
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
