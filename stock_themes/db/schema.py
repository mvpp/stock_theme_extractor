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

CREATE TABLE IF NOT EXISTS open_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES stocks(ticker),
    theme_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    distinctiveness REAL DEFAULT 0.0,
    source TEXT NOT NULL,
    evidence TEXT,
    mapped_canonical TEXT,
    mapped_similarity REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_themes_theme ON stock_themes(theme_id);
CREATE INDEX IF NOT EXISTS idx_stock_themes_confidence ON stock_themes(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_stocks_market_cap ON stocks(market_cap DESC);
CREATE INDEX IF NOT EXISTS idx_social_ticker_date ON social_messages(ticker, collected_at);
CREATE INDEX IF NOT EXISTS idx_open_themes_ticker ON open_themes(ticker);
CREATE INDEX IF NOT EXISTS idx_open_themes_text ON open_themes(theme_text);
CREATE INDEX IF NOT EXISTS idx_open_themes_confidence ON open_themes(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_open_themes_source ON open_themes(source);
"""

# Migrations for existing databases (additive only — safe to re-run)
MIGRATIONS_SQL = """
-- Add freshness column to open_themes (time decay score at extraction time)
ALTER TABLE open_themes ADD COLUMN freshness REAL DEFAULT NULL;

-- Dashboard: daily aggregate metrics per theme (regime, ranking, momentum)
CREATE TABLE IF NOT EXISTS theme_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    stock_count INTEGER NOT NULL,
    total_market_cap REAL,
    avg_confidence REAL,
    avg_freshness REAL,
    news_mention_count INTEGER DEFAULT 0,
    source_breakdown TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_date, theme_name)
);

-- Dashboard: per-stock theme membership per snapshot (drift detection)
CREATE TABLE IF NOT EXISTS theme_stock_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT,
    UNIQUE(snapshot_date, theme_name, ticker)
);

-- Dashboard: audit trail for human-in-the-loop promotions
CREATE TABLE IF NOT EXISTS promotion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_theme_text TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    parent_theme TEXT,
    category TEXT,
    promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stock_count_at_promotion INTEGER,
    avg_confidence_at_promotion REAL
);

CREATE INDEX IF NOT EXISTS idx_theme_snap_date ON theme_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_theme_snap_name ON theme_snapshots(theme_name);
CREATE INDEX IF NOT EXISTS idx_tss_theme_date ON theme_stock_snapshots(theme_name, snapshot_date);

-- 13F investor holding changes
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
);

CREATE INDEX IF NOT EXISTS idx_investor_ticker ON investor_holdings(ticker);
CREATE INDEX IF NOT EXISTS idx_investor_change ON investor_holdings(change_type);
CREATE INDEX IF NOT EXISTS idx_open_themes_source_text ON open_themes(source, theme_text);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Initialize the database and return a connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    # Run additive migrations (safe to re-run)
    # Strip SQL comments before splitting on ';' so comment-prefixed
    # statements aren't accidentally skipped.
    cleaned = "\n".join(
        line for line in MIGRATIONS_SQL.splitlines()
        if not line.strip().startswith("--")
    )
    for statement in cleaned.strip().split(";"):
        stmt = statement.strip()
        if not stmt:
            continue
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column/table already exists
    conn.commit()
    return conn
