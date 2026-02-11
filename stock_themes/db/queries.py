"""Convenience query functions that wrap ThemeStore."""

from __future__ import annotations

from stock_themes.db.store import ThemeStore


def lookup(ticker: str, db_path: str = "stock_themes.db") -> list[dict]:
    """Quick lookup: return themes for a single ticker."""
    store = ThemeStore(db_path)
    try:
        return store.get_themes_for_stock(ticker)
    finally:
        store.close()


def find_stocks(theme_name: str, db_path: str = "stock_themes.db",
                min_confidence: float = 0.3) -> list[dict]:
    """Find all stocks matching a theme."""
    store = ThemeStore(db_path)
    try:
        return store.get_stocks_for_theme(theme_name, min_confidence)
    finally:
        store.close()


def stats(db_path: str = "stock_themes.db") -> dict:
    """Return database statistics."""
    store = ThemeStore(db_path)
    try:
        conn = store.conn
        stock_count = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        theme_count = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        assoc_count = conn.execute("SELECT COUNT(*) FROM stock_themes").fetchone()[0]
        msg_count = conn.execute("SELECT COUNT(*) FROM social_messages").fetchone()[0]
        return {
            "stocks": stock_count,
            "themes": theme_count,
            "associations": assoc_count,
            "social_messages": msg_count,
        }
    finally:
        store.close()
