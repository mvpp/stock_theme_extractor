import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    sic_code TEXT,
    market_cap REAL,
    exchange TEXT,
    patent_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS stock_themes (
    ticker TEXT REFERENCES stocks(ticker),
    theme_id INTEGER REFERENCES themes(id),
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    evidence TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, theme_id)
);

CREATE TABLE IF NOT EXISTS social_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'stocktwits',
    message_id TEXT,
    body TEXT NOT NULL,
    sentiment TEXT,
    created_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, message_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_themes_theme ON stock_themes(theme_id);
CREATE INDEX IF NOT EXISTS idx_stock_themes_confidence ON stock_themes(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_stocks_market_cap ON stocks(market_cap DESC);
CREATE INDEX IF NOT EXISTS idx_social_ticker_date ON social_messages(ticker, collected_at);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Initialize the database and return a connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
