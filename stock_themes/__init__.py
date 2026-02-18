"""Stock Themes: Generate investment themes for stock tickers."""

from __future__ import annotations

from stock_themes.models import ThemeResult


def get_themes(
    ticker: str,
    use_llm: bool = True,
    max_themes: int = 10,
    db_path: str | None = None,
) -> ThemeResult:
    """Generate investment themes for a single stock ticker.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL").
        use_llm: Whether to use LLM extraction (requires LLM API key for chosen provider).
        max_themes: Maximum themes to return.
        db_path: If provided, also save results to this SQLite database.

    Returns:
        ThemeResult with ranked themes.
    """
    from stock_themes.data.pipeline import DataPipeline
    from stock_themes.extraction.ensemble import EnsembleExtractor

    pipeline = DataPipeline()
    profile = pipeline.fetch(ticker)

    extractor = EnsembleExtractor(use_llm=use_llm, max_themes=max_themes)
    result = extractor.extract(profile)

    if db_path:
        from stock_themes.db.store import ThemeStore
        store = ThemeStore(db_path)
        store.save_theme_result(result)
        store.close()

    return result


def build_database(
    db_path: str = "stock_themes.db",
    llm_market_cap_threshold: float = 1e9,
    max_themes_per_stock: int = 10,
    skip_existing: bool = True,
) -> None:
    """Build the full stock themes database for all US stocks.

    Args:
        db_path: Path to SQLite database file.
        llm_market_cap_threshold: Market cap threshold for LLM extraction.
        max_themes_per_stock: Max themes per stock.
        skip_existing: Skip tickers already in the database.
    """
    from stock_themes.batch import run_batch

    run_batch(
        db_path=db_path,
        llm_market_cap_threshold=llm_market_cap_threshold,
        max_themes_per_stock=max_themes_per_stock,
        skip_existing=skip_existing,
    )
