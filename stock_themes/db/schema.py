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

-- Daily price data (rolling 60 trading days)
CREATE TABLE IF NOT EXISTS stock_prices (
    ticker TEXT NOT NULL,
    price_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, price_date)
);
CREATE INDEX IF NOT EXISTS idx_sp_ticker ON stock_prices(ticker);
CREATE INDEX IF NOT EXISTS idx_sp_date ON stock_prices(price_date);

-- Per-stock technicals (upserted daily, one row per ticker)
CREATE TABLE IF NOT EXISTS stock_technicals (
    ticker TEXT PRIMARY KEY,
    price_date TEXT NOT NULL,
    close_price REAL,
    ma20 REAL,
    ma20_distance_pct REAL,
    volume_20d_avg INTEGER,
    volume_trend REAL,
    analyst_target REAL,
    analyst_upside_pct REAL,
    analyst_count INTEGER,
    recommendation_mean REAL,
    positive_surprises INTEGER,
    gross_margin REAL,
    operating_margin REAL,
    profit_margin REAL,
    return_on_equity REAL,
    return_on_assets REAL,
    debt_to_equity REAL,
    current_ratio REAL,
    free_cashflow REAL,
    operating_cashflow REAL,
    trailing_pe REAL,
    forward_pe REAL,
    peg_ratio REAL,
    beta REAL,
    dividend_yield REAL,
    earnings_growth REAL,
    revenue_growth REAL,
    trailing_eps REAL,
    forward_eps REAL,
    held_pct_institutions REAL,
    short_pct_of_float REAL,
    short_ratio REAL,
    insider_buy_count INTEGER,
    insider_sell_count INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Theme-level aggregated technicals per day
CREATE TABLE IF NOT EXISTS theme_technicals (
    theme_name TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    avg_ma20_distance_pct REAL,
    pct_above_ma20 REAL,
    avg_volume_trend REAL,
    avg_analyst_upside_pct REAL,
    avg_positive_surprises REAL,
    PRIMARY KEY (theme_name, snapshot_date)
);

-- Regime scores with upgrade/downgrade hysteresis
CREATE TABLE IF NOT EXISTS regime_scores (
    theme_name TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    regime_score REAL NOT NULL,
    regime_label TEXT NOT NULL,
    regime_direction TEXT NOT NULL,
    watch_status TEXT,
    watch_since TEXT,
    signal_components TEXT,
    PRIMARY KEY (theme_name, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_rs_theme ON regime_scores(theme_name);
CREATE INDEX IF NOT EXISTS idx_rs_date ON regime_scores(snapshot_date);

-- Pipeline run tracking for data freshness
CREATE TABLE IF NOT EXISTS pipeline_runs (
    pipeline_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    status TEXT NOT NULL,
    tickers_processed INTEGER,
    tickers_failed INTEGER,
    error_message TEXT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pipeline_name, run_date)
);
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
