from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from stock_themes.db.schema import init_db
from stock_themes.models import CompanyProfile, Theme, ThemeResult, SocialMessage, ExtractionMethod


class ThemeStore:
    """CRUD operations for the stock themes database."""

    def __init__(self, db_path: str | Path = "stock_themes.db"):
        self.db_path = str(db_path)
        self.conn = init_db(self.db_path)

    def close(self):
        self.conn.close()

    # --- Stocks ---

    def upsert_stock(self, profile: CompanyProfile) -> None:
        self.conn.execute(
            """INSERT INTO stocks (ticker, name, sector, industry, sic_code,
               market_cap, exchange, patent_count, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(ticker) DO UPDATE SET
                 name=excluded.name, sector=excluded.sector,
                 industry=excluded.industry, sic_code=excluded.sic_code,
                 market_cap=excluded.market_cap, exchange=excluded.exchange,
                 patent_count=excluded.patent_count, updated_at=CURRENT_TIMESTAMP""",
            (
                profile.ticker,
                profile.name,
                profile.sector,
                profile.industry,
                profile.sic_code,
                profile.market_cap,
                profile.exchange,
                profile.patent_count,
            ),
        )
        self.conn.commit()

    def get_stock(self, ticker: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM stocks WHERE ticker = ?", (ticker.upper(),)
        ).fetchone()
        return dict(row) if row else None

    def get_all_tickers(self) -> list[str]:
        rows = self.conn.execute("SELECT ticker FROM stocks ORDER BY ticker").fetchall()
        return [row["ticker"] for row in rows]

    def get_tickers_updated_since(self, since: str | None = None) -> list[str]:
        """Return tickers updated on or after `since` (ISO date string, e.g. '2025-01-01').

        When `since` is None, returns all tickers (same as get_all_tickers()).
        Used by run_batch() to determine which tickers to skip during a refresh run:
        tickers NOT in this set will be re-processed.
        """
        if since is None:
            return self.get_all_tickers()
        rows = self.conn.execute(
            "SELECT ticker FROM stocks WHERE updated_at >= ? ORDER BY ticker",
            (since,),
        ).fetchall()
        return [row["ticker"] for row in rows]

    def stock_exists(self, ticker: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM stocks WHERE ticker = ?", (ticker.upper(),)
        ).fetchone()
        return row is not None

    # --- Themes ---

    def ensure_theme(self, name: str, category: str | None = None,
                     description: str | None = None) -> int:
        """Insert theme if not exists, return theme id."""
        row = self.conn.execute(
            "SELECT id FROM themes WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row["id"]
        cursor = self.conn.execute(
            "INSERT INTO themes (name, category, description) VALUES (?, ?, ?)",
            (name, category, description),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_theme_id(self, name: str) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM themes WHERE name = ?", (name,)
        ).fetchone()
        return row["id"] if row else None

    # --- Stock-Theme associations ---

    def upsert_stock_theme(self, ticker: str, theme_name: str, confidence: float,
                           source: str, evidence: str | None = None,
                           category: str | None = None,
                           description: str | None = None) -> None:
        theme_id = self.ensure_theme(theme_name, category, description)
        self.conn.execute(
            """INSERT INTO stock_themes (ticker, theme_id, confidence, source, evidence, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(ticker, theme_id) DO UPDATE SET
                 confidence=excluded.confidence, source=excluded.source,
                 evidence=excluded.evidence, updated_at=CURRENT_TIMESTAMP""",
            (ticker.upper(), theme_id, confidence, source, evidence),
        )
        self.conn.commit()

    def save_theme_result(self, result: ThemeResult) -> None:
        """Save a full ThemeResult atomically — all-or-nothing.

        Uses a single SQLite transaction so a crash mid-save leaves no partial
        data: the ticker will not appear in `stocks` and will be retried on the
        next build_database() run.
        """
        with self.conn:
            # Upsert stock row
            self.conn.execute(
                """INSERT INTO stocks
                       (ticker, name, sector, industry, sic_code,
                        market_cap, exchange, patent_count, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(ticker) DO UPDATE SET
                       name=excluded.name, sector=excluded.sector,
                       industry=excluded.industry, sic_code=excluded.sic_code,
                       market_cap=excluded.market_cap, exchange=excluded.exchange,
                       patent_count=excluded.patent_count,
                       updated_at=CURRENT_TIMESTAMP""",
                (
                    result.ticker, result.profile.name, result.profile.sector,
                    result.profile.industry, result.profile.sic_code,
                    result.profile.market_cap, result.profile.exchange,
                    result.profile.patent_count or 0,
                ),
            )
            # Replace themes atomically
            self.conn.execute(
                "DELETE FROM stock_themes WHERE ticker = ?", (result.ticker,)
            )
            for theme in result.themes:
                # Upsert theme row (inline to stay inside the transaction)
                self.conn.execute(
                    """INSERT INTO themes (name, category, description)
                       VALUES (?, ?, ?)
                       ON CONFLICT(name) DO UPDATE SET
                           category=excluded.category,
                           description=excluded.description""",
                    (theme.name, theme.canonical_category, None),
                )
                row = self.conn.execute(
                    "SELECT id FROM themes WHERE name = ?", (theme.name,)
                ).fetchone()
                self.conn.execute(
                    """INSERT INTO stock_themes
                           (ticker, theme_id, confidence, source, evidence, updated_at)
                       VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (result.ticker, row["id"], theme.confidence,
                     theme.source.value, theme.evidence),
                )
        # with-block commits on clean exit, rolls back on any exception

    def get_themes_for_stock(self, ticker: str,
                             min_confidence: float = 0.0) -> list[dict]:
        rows = self.conn.execute(
            """SELECT t.name, t.category, st.confidence, st.source, st.evidence
               FROM stock_themes st
               JOIN themes t ON t.id = st.theme_id
               WHERE st.ticker = ? AND st.confidence >= ?
               ORDER BY st.confidence DESC""",
            (ticker.upper(), min_confidence),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stocks_for_theme(self, theme_name: str,
                             min_confidence: float = 0.0) -> list[dict]:
        rows = self.conn.execute(
            """SELECT s.ticker, s.name, s.market_cap, st.confidence, st.source
               FROM stock_themes st
               JOIN stocks s ON s.ticker = st.ticker
               JOIN themes t ON t.id = st.theme_id
               WHERE t.name = ? AND st.confidence >= ?
               ORDER BY st.confidence DESC""",
            (theme_name, min_confidence),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_theme_distribution(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT t.name, t.category, COUNT(*) as stock_count,
                      AVG(st.confidence) as avg_confidence
               FROM stock_themes st
               JOIN themes t ON t.id = st.theme_id
               GROUP BY t.name
               ORDER BY stock_count DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Social messages ---

    def store_social_messages(self, messages: list[SocialMessage]) -> int:
        """Store social messages, skip duplicates. Returns count inserted."""
        inserted = 0
        for msg in messages:
            try:
                self.conn.execute(
                    """INSERT INTO social_messages
                       (ticker, source, message_id, body, sentiment,
                        created_at, collected_at)
                       VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (msg.ticker, msg.source, msg.message_id, msg.body,
                     msg.sentiment, msg.created_at),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass  # duplicate message_id
        self.conn.commit()
        return inserted

    def get_social_text(self, ticker: str, days: int = 30,
                        sentiment_filter: list[str] | None = None) -> str:
        """Get aggregated social message text for a ticker.

        Args:
            sentiment_filter: List of sentiments to include.
                              e.g. ["bullish", None] for positive + neutral.
                              None means include all.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        if sentiment_filter is not None:
            placeholders = ",".join("?" for _ in sentiment_filter)
            # Handle NULL sentiment (neutral) — SQLite needs IS NULL
            has_null = None in sentiment_filter
            non_null = [s for s in sentiment_filter if s is not None]

            conditions = []
            params: list = [ticker.upper(), cutoff.isoformat()]
            if non_null:
                placeholders = ",".join("?" for _ in non_null)
                conditions.append(f"sentiment IN ({placeholders})")
                params.extend(non_null)
            if has_null:
                conditions.append("sentiment IS NULL")

            where_clause = " OR ".join(conditions)
            query = f"""SELECT body FROM social_messages
                        WHERE ticker = ? AND collected_at >= ?
                        AND ({where_clause})
                        ORDER BY collected_at"""
        else:
            query = """SELECT body FROM social_messages
                       WHERE ticker = ? AND collected_at >= ?
                       ORDER BY collected_at"""
            params = [ticker.upper(), cutoff.isoformat()]

        rows = self.conn.execute(query, params).fetchall()
        return " ".join(row["body"] for row in rows)
