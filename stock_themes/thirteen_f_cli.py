"""Standalone 13F investor holdings processor.

Runs independently of the main build_database() pipeline.
Fetches 13F data for all tracked investors, matches to stocks
already in the database, and writes open_themes with source="13f".

Usage:
    python -m stock_themes.thirteen_f_cli [--db stock_themes.db]
"""

from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def build_investor_themes(db_path: str = "stock_themes.db") -> dict:
    """Fetch 13F data and write investor themes to the database.

    This function can be called from cron on a quarterly schedule
    (separate from the main daily/weekly build_database runs).

    Returns:
        Dict with statistics.
    """
    from stock_themes.data.thirteen_f import ThirteenFProvider
    from stock_themes.extraction.investor_extractor import InvestorHoldingExtractor
    from stock_themes.db.store import ThemeStore
    from stock_themes.models import OpenTheme

    stats = {"investors_processed": 0, "tickers_with_changes": 0, "themes_written": 0}

    provider = ThirteenFProvider()
    if not provider.is_available():
        logger.error("13F provider not available (check SEC_EDGAR_EMAIL in .env)")
        return stats

    # Fetch all investor changes
    investor_changes = provider.fetch_all_investors(db_path=db_path)
    stats["tickers_with_changes"] = len(investor_changes)

    if not investor_changes:
        logger.info("No investor holding changes found")
        return stats

    # Write themes to database
    store = ThemeStore(db_path)
    extractor = InvestorHoldingExtractor(investor_changes)

    for ticker, changes in investor_changes.items():
        if not store.stock_exists(ticker):
            continue

        # Remove existing 13F themes for this ticker
        store.conn.execute(
            "DELETE FROM open_themes WHERE ticker = ? AND source = '13f'",
            (ticker,),
        )

        # Generate and insert new themes
        from stock_themes.models import CompanyProfile
        dummy_profile = CompanyProfile(ticker=ticker, name="")
        themes = extractor.extract(dummy_profile)

        for ot in themes:
            store.conn.execute(
                """INSERT INTO open_themes
                       (ticker, theme_text, confidence, distinctiveness,
                        source, evidence, freshness, updated_at)
                   VALUES (?, ?, ?, 0.0, '13f', ?, NULL, CURRENT_TIMESTAMP)""",
                (ticker, ot.text, ot.confidence, ot.evidence),
            )
            stats["themes_written"] += 1

    store.conn.commit()
    store.close()

    summary = (
        f"13F: {stats['tickers_with_changes']} tickers with changes, "
        f"{stats['themes_written']} themes written"
    )
    print(summary)
    logger.info(summary)
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Build investor holding themes from 13F filings"
    )
    parser.add_argument(
        "--db", default="stock_themes.db",
        help="Path to SQLite database (default: stock_themes.db)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    build_investor_themes(db_path=args.db)


if __name__ == "__main__":
    main()
