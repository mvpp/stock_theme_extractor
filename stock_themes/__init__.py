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
    profile = pipeline.fetch(ticker, db_path=db_path)

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
    max_tickers: int | None = None,
    refresh_after: str | None = None,
    log_file: str | None = None,
) -> dict:
    """Build the full stock themes database for all US stocks.

    Args:
        db_path: Path to SQLite database file.
        llm_market_cap_threshold: Market cap threshold for LLM extraction.
        max_themes_per_stock: Max themes per stock.
        skip_existing: Skip tickers already in the database.
        max_tickers: If set, process at most this many tickers per run.
            Use with a cron job to spread the build across days:
            ``build_database(max_tickers=250)`` every 40 minutes.
        refresh_after: ISO date string (e.g. "2025-01-01"). Tickers last
            updated before this date are treated as unprocessed and will be
            re-queued. Use for seasonal rebuilds alongside max_tickers.
        log_file: Path to log file. Defaults to <db_path>.log (e.g.
            stock_themes.log next to stock_themes.db). Logs are appended
            across runs so you can review the full build history with
            ``grep WARNING stock_themes.log`` after a broken run.

    Returns:
        Dict with batch statistics (processed, failed, skipped, total).
    """
    import logging
    from pathlib import Path

    if log_file is None:
        log_file = str(Path(db_path).with_suffix(".log"))

    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Console handler — only add once per process to avoid duplicate lines
    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)

    # File handler — always append so logs survive SSH session drops
    fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    print(f"Logging to {log_file}")

    from stock_themes.batch import run_batch

    return run_batch(
        db_path=db_path,
        llm_market_cap_threshold=llm_market_cap_threshold,
        max_themes_per_stock=max_themes_per_stock,
        skip_existing=skip_existing,
        max_tickers=max_tickers,
        refresh_after=refresh_after,
    )
