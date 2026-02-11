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
from stock_themes.data.patents import PatentsViewProvider
from stock_themes.data.news import GDELTProvider
from stock_themes.data.social import get_monthly_social_text
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

    # Set up pipeline and extractors
    pipeline = DataPipeline()
    patents_provider = PatentsViewProvider()
    news_provider = GDELTProvider()

    # Process in batches
    for ticker in tqdm(tickers_to_process, desc="Processing stocks"):
        try:
            _process_single(
                ticker=ticker,
                pipeline=pipeline,
                patents_provider=patents_provider,
                news_provider=news_provider,
                store=store,
                db_path=db_path,
                max_themes=max_themes_per_stock,
                use_llm=True,
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
    patents_provider: PatentsViewProvider,
    news_provider: GDELTProvider,
    store: ThemeStore,
    db_path: str,
    max_themes: int,
    use_llm: bool,
) -> None:
    """Process a single ticker: fetch data, extract themes, save to DB."""

    # 1. Core data (Yahoo + SEC EDGAR)
    profile = pipeline.fetch(ticker)

    # 2. Enrichment: Patents
    if profile.name:
        try:
            patent_data = patents_provider.fetch_with_name(ticker, profile.name)
            profile.patent_titles = patent_data.patent_titles
            profile.patent_cpc_codes = patent_data.patent_cpc_codes
            profile.patent_count = patent_data.patent_count
            if "patentsview" not in profile.data_sources:
                profile.data_sources.append("patentsview")
        except Exception as e:
            logger.debug(f"{ticker}: PatentsView failed: {e}")

    # 3. Enrichment: News
    if profile.name:
        try:
            news_data = news_provider.fetch_with_name(ticker, profile.name)
            profile.news_themes = news_data.news_themes
            profile.news_titles = news_data.news_titles
            profile.news_tone = news_data.news_tone
            if "gdelt" not in profile.data_sources:
                profile.data_sources.append("gdelt")
        except Exception as e:
            logger.debug(f"{ticker}: GDELT failed: {e}")

    # 4. Enrichment: Social (from accumulated daily messages)
    try:
        social_text = get_monthly_social_text(db_path, ticker)
        if social_text:
            profile.social_text = social_text
            if "stocktwits" not in profile.data_sources:
                profile.data_sources.append("stocktwits")
    except Exception as e:
        logger.debug(f"{ticker}: Social text failed: {e}")

    # 5. Extract themes
    extractor = EnsembleExtractor(use_llm=use_llm, max_themes=max_themes)
    result = extractor.extract(profile)

    # 6. Save to database
    store.save_theme_result(result)

    # Rate limit for LLM calls
    market_cap = profile.market_cap or 0
    if use_llm and market_cap >= LLM_MARKET_CAP_THRESHOLD:
        time.sleep(LLM_DELAY_SECONDS)
