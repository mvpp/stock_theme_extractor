#!/usr/bin/env python3
"""Populate API-facing tables (FTS index, 13F holdings) from core library data.

Run after the extraction pipeline, alongside take_snapshot.py:
    python scripts/populate_api_tables.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Add project root to path so we can import stock_themes
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from stock_themes.db.schema import init_db
from stock_themes.config import settings


def populate_fts(conn: sqlite3.Connection) -> int:
    """Rebuild the FTS5 index from canonical themes."""
    # Ensure FTS table exists
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS theme_fts "
            "USING fts5(name, description, category)"
        )
    except sqlite3.OperationalError:
        pass

    conn.execute("DELETE FROM theme_fts")

    # Import theme descriptions from taxonomy
    try:
        from stock_themes.taxonomy.themes import THEME_DESCRIPTIONS, THEME_CATEGORIES
        count = 0
        for theme_name, description in THEME_DESCRIPTIONS.items():
            category = THEME_CATEGORIES.get(theme_name, "")
            conn.execute(
                "INSERT OR IGNORE INTO theme_fts(name, description, category) VALUES (?, ?, ?)",
                (theme_name, description, category),
            )
            count += 1
        conn.commit()
        print(f"  FTS index: {count} theme descriptions indexed")
        return count
    except ImportError:
        # Fallback: use themes table
        result = conn.execute(
            "INSERT INTO theme_fts(name, description, category) "
            "SELECT name, COALESCE(description, ''), COALESCE(category, '') FROM themes"
        )
        conn.commit()
        count = result.rowcount
        print(f"  FTS index: {count} themes from DB indexed")
        return count


def populate_investor_holdings(conn: sqlite3.Connection) -> int:
    """Populate investor_holdings table from 13F data."""
    # Ensure table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investor_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            investor_name TEXT NOT NULL,
            investor_short TEXT NOT NULL,
            change_type TEXT NOT NULL,
            shares_current INTEGER,
            shares_previous INTEGER,
            pct_change REAL,
            filing_date TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, investor_short)
        )
    """)

    try:
        from stock_themes.data.thirteen_f import ThirteenFProvider
        provider = ThirteenFProvider()
        all_changes = provider.fetch_all_investors()

        count = 0
        for change in all_changes:
            ticker = change.get("ticker")
            if not ticker:
                continue

            conn.execute(
                """INSERT OR REPLACE INTO investor_holdings
                   (ticker, investor_name, investor_short, change_type,
                    shares_current, shares_previous, pct_change, filing_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticker,
                    change.get("investor_name", ""),
                    change.get("investor_short", ""),
                    change.get("change_type", "unknown"),
                    change.get("shares_current"),
                    change.get("shares_previous"),
                    change.get("pct_change"),
                    change.get("filing_date"),
                ),
            )
            count += 1

        conn.commit()
        print(f"  Investor holdings: {count} records written")
        return count
    except ImportError as e:
        print(f"  Investor holdings: skipped ({e})")
        return 0
    except Exception as e:
        print(f"  Investor holdings: error ({e})")
        return 0


def main():
    db_path = settings.get("db_path", "stock_themes.db")
    print(f"Populating API tables in {db_path}")

    conn = init_db(db_path)
    try:
        populate_fts(conn)
        populate_investor_holdings(conn)
    finally:
        conn.close()

    print("Done!")


if __name__ == "__main__":
    main()
