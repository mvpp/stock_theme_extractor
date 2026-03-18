"""Self-contained database layer — no dependency on stock_themes.

Combines schema init, read queries (from ThemeStore), and convenience
query functions (from queries.py) into a single module.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from themes_api import config

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

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

MIGRATIONS_SQL = """
ALTER TABLE open_themes ADD COLUMN freshness REAL DEFAULT NULL;

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

CREATE TABLE IF NOT EXISTS theme_stock_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT,
    UNIQUE(snapshot_date, theme_name, ticker)
);

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

-- 13F investor holding changes (populated by core batch)
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
    # FTS5 virtual table for full-text theme search
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS theme_fts "
            "USING fts5(name, description, category)"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn


def get_conn() -> sqlite3.Connection:
    """Get a new DB connection using the configured path."""
    return init_db(config.DB_PATH)


# ---------------------------------------------------------------------------
# Read queries (extracted from ThemeStore)
# ---------------------------------------------------------------------------

def get_stock(conn: sqlite3.Connection, ticker: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM stocks WHERE ticker = ?", (ticker.upper(),)
    ).fetchone()
    return dict(row) if row else None


def get_all_tickers(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT ticker FROM stocks ORDER BY ticker").fetchall()
    return [row["ticker"] for row in rows]


def get_themes_for_stock(conn: sqlite3.Connection, ticker: str,
                         min_confidence: float = 0.0) -> list[dict]:
    rows = conn.execute(
        """SELECT t.name, t.category, st.confidence, st.source, st.evidence
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           WHERE st.ticker = ? AND st.confidence >= ?
           ORDER BY st.confidence DESC""",
        (ticker.upper(), min_confidence),
    ).fetchall()
    return [dict(r) for r in rows]


def get_stocks_for_theme(conn: sqlite3.Connection, theme_name: str,
                         min_confidence: float = 0.0) -> list[dict]:
    rows = conn.execute(
        """SELECT s.ticker, s.name, s.market_cap, st.confidence, st.source
           FROM stock_themes st
           JOIN stocks s ON s.ticker = st.ticker
           JOIN themes t ON t.id = st.theme_id
           WHERE t.name = ? AND st.confidence >= ?
           ORDER BY st.confidence DESC""",
        (theme_name, min_confidence),
    ).fetchall()
    return [dict(r) for r in rows]


def get_stocks_for_themes(conn: sqlite3.Connection, theme_names: list[str],
                          min_confidence: float = 0.0) -> list[dict]:
    if not theme_names:
        return []
    placeholders = ",".join("?" for _ in theme_names)
    rows = conn.execute(
        f"""SELECT s.ticker, s.name, s.market_cap,
                   st.confidence, st.source, t.name as theme_name
            FROM stock_themes st
            JOIN stocks s ON s.ticker = st.ticker
            JOIN themes t ON t.id = st.theme_id
            WHERE t.name IN ({placeholders}) AND st.confidence >= ?
            ORDER BY st.confidence DESC""",
        (*theme_names, min_confidence),
    ).fetchall()
    return [dict(r) for r in rows]


def get_theme_distribution(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT t.name, t.category, COUNT(*) as stock_count,
                  AVG(st.confidence) as avg_confidence
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           GROUP BY t.name
           ORDER BY stock_count DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_filtered_open_themes(conn: sqlite3.Connection, ticker: str,
                             min_confidence: float = 0.5,
                             min_distinctiveness: float = 0.15,
                             max_mapped_similarity: float = 0.85) -> list[dict]:
    rows = conn.execute(
        """SELECT theme_text, confidence, distinctiveness, source,
                  evidence, mapped_canonical, mapped_similarity
           FROM open_themes
           WHERE ticker = ?
             AND confidence >= ?
             AND distinctiveness >= ?
             AND (mapped_similarity IS NULL OR mapped_similarity <= ?)
           ORDER BY confidence DESC""",
        (ticker.upper(), min_confidence, min_distinctiveness,
         max_mapped_similarity),
    ).fetchall()
    return [dict(r) for r in rows]


def get_open_themes(conn: sqlite3.Connection, ticker: str) -> list[dict]:
    rows = conn.execute(
        """SELECT theme_text, confidence, distinctiveness, source,
                  evidence, mapped_canonical, mapped_similarity
           FROM open_themes WHERE ticker = ?
           ORDER BY confidence DESC""",
        (ticker.upper(),),
    ).fetchall()
    return [dict(r) for r in rows]


def search_open_themes(conn: sqlite3.Connection, query: str,
                       min_confidence: float = 0.5,
                       min_distinctiveness: float = 0.15,
                       max_mapped_similarity: float = 0.85) -> list[dict]:
    rows = conn.execute(
        """SELECT s.ticker, s.name, s.market_cap,
                  ot.theme_text, ot.confidence, ot.distinctiveness,
                  ot.source, ot.mapped_canonical, ot.mapped_similarity
           FROM open_themes ot
           JOIN stocks s ON s.ticker = ot.ticker
           WHERE ot.theme_text LIKE ?
             AND ot.confidence >= ?
             AND ot.distinctiveness >= ?
             AND (ot.mapped_similarity IS NULL OR ot.mapped_similarity <= ?)
           ORDER BY ot.confidence DESC""",
        (f"%{query}%", min_confidence, min_distinctiveness,
         max_mapped_similarity),
    ).fetchall()
    return [dict(r) for r in rows]


def get_promotion_candidates(conn: sqlite3.Connection,
                             min_stock_count: int = 5,
                             min_avg_confidence: float = 0.6,
                             min_avg_distinctiveness: float = 0.3) -> list[dict]:
    rows = conn.execute(
        """SELECT theme_text,
                  COUNT(*) as stock_count,
                  AVG(confidence) as avg_confidence,
                  AVG(distinctiveness) as avg_distinctiveness,
                  GROUP_CONCAT(ticker, ', ') as tickers,
                  mapped_canonical,
                  AVG(mapped_similarity) as avg_mapped_similarity
           FROM open_themes
           GROUP BY theme_text
           HAVING stock_count >= ?
              AND avg_confidence >= ?
              AND avg_distinctiveness >= ?
           ORDER BY stock_count DESC, avg_confidence DESC""",
        (min_stock_count, min_avg_confidence, min_avg_distinctiveness),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Convenience query functions (from queries.py, config imports replaced)
# ---------------------------------------------------------------------------

def get_all_themes(conn: sqlite3.Connection, ticker: str,
                   min_confidence: float = 0.0) -> list[dict]:
    """Return canonical + quality-filtered open themes for a ticker."""
    canonical = get_themes_for_stock(conn, ticker, min_confidence)
    results: list[dict] = []
    canonical_names: set[str] = set()
    for t in canonical:
        results.append({
            "name": t["name"],
            "confidence": t["confidence"],
            "source": t["source"],
            "evidence": t["evidence"],
            "tier": "canonical",
            "category": t["category"],
        })
        canonical_names.add(t["name"])

    min_conf_floor = min(
        config.THRESHOLDS["llm"]["min_confidence"],
        config.THRESHOLDS["narrative"]["min_confidence"],
    )
    min_dist_floor = min(
        config.THRESHOLDS["llm"]["min_distinctiveness"],
        config.THRESHOLDS["narrative"]["min_distinctiveness"],
    )
    open_rows = get_filtered_open_themes(
        conn, ticker,
        min_confidence=min_conf_floor,
        min_distinctiveness=min_dist_floor,
        max_mapped_similarity=config.MAX_MAPPED_SIMILARITY,
    )

    w_conf = config.QUALITY_WEIGHTS["confidence"]
    w_dist = config.QUALITY_WEIGHTS["distinctiveness"]

    for ot in open_rows:
        src = ot["source"]
        thresh = config.THRESHOLDS.get(src, config.THRESHOLDS["llm"])

        if ot["confidence"] < thresh["min_confidence"]:
            continue
        if ot["distinctiveness"] < thresh["min_distinctiveness"]:
            continue

        quality = w_conf * ot["confidence"] + w_dist * ot["distinctiveness"]
        if quality < thresh["min_quality"]:
            continue

        if ot.get("mapped_canonical") and ot["mapped_canonical"] in canonical_names:
            continue

        results.append({
            "name": ot["theme_text"],
            "confidence": ot["confidence"],
            "source": ot["source"],
            "evidence": ot["evidence"],
            "tier": "open",
            "distinctiveness": ot["distinctiveness"],
            "quality_score": round(quality, 3),
            "mapped_canonical": ot.get("mapped_canonical"),
            "mapped_similarity": ot.get("mapped_similarity"),
        })

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results


def find_stocks(conn: sqlite3.Connection, theme_name: str,
                min_confidence: float = 0.3,
                include_descendants: bool = True,
                fallback_open: bool = True) -> list[dict]:
    """Find all stocks matching a theme, optionally including descendants."""
    results: list[dict] = []
    if include_descendants:
        from themes_api.taxonomy import get_theme_tree
        tree = get_theme_tree()
        descendants = tree.get_descendants(theme_name)
        if descendants:
            all_names = [theme_name] + descendants
            results = get_stocks_for_themes(conn, all_names, min_confidence)

    if not results:
        results = get_stocks_for_theme(conn, theme_name, min_confidence)

    if not results and fallback_open:
        thresh = config.THRESHOLDS["llm"]
        open_results = search_open_themes(
            conn, theme_name,
            min_confidence=thresh["min_confidence"],
            min_distinctiveness=thresh["min_distinctiveness"],
            max_mapped_similarity=config.MAX_MAPPED_SIMILARITY,
        )
        for r in open_results:
            r["tier"] = "open"
            r["theme_name"] = r.pop("theme_text", theme_name)
        results = open_results

    return results


def suggest_promotions(conn: sqlite3.Connection) -> list[dict]:
    """Identify open themes ready for promotion to canonical."""
    candidates = get_promotion_candidates(
        conn,
        min_stock_count=config.PROMOTION["min_stock_count"],
        min_avg_confidence=config.PROMOTION["min_avg_confidence"],
        min_avg_distinctiveness=config.PROMOTION["min_avg_distinctiveness"],
    )

    w_c = config.QUALITY_WEIGHTS["confidence"]
    w_d = config.QUALITY_WEIGHTS["distinctiveness"]

    results = []
    for c in candidates:
        avg_quality = w_c * c["avg_confidence"] + w_d * c["avg_distinctiveness"]
        if avg_quality < config.PROMOTION["min_avg_quality"]:
            continue
        c["avg_quality"] = round(avg_quality, 3)
        results.append(c)
    return results


# ---------------------------------------------------------------------------
# New query functions for expanded dashboard
# ---------------------------------------------------------------------------

def populate_fts(conn: sqlite3.Connection) -> int:
    """Rebuild the FTS5 index from the themes table."""
    conn.execute("DELETE FROM theme_fts")
    result = conn.execute(
        "INSERT INTO theme_fts(name, description, category) "
        "SELECT name, COALESCE(description, ''), COALESCE(category, '') FROM themes"
    )
    conn.commit()
    return result.rowcount


def search_fts(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Full-text search on canonical themes using FTS5."""
    # Tokenize and add * for prefix matching
    tokens = query.strip().split()
    fts_query = " OR ".join(f'"{t}"*' for t in tokens if t)
    if not fts_query:
        return []
    try:
        rows = conn.execute(
            """SELECT name, description, category, rank
               FROM theme_fts WHERE theme_fts MATCH ?
               ORDER BY rank LIMIT 50""",
            (fts_query,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def get_open_themes_for_canonical(conn: sqlite3.Connection,
                                   canonical_name: str) -> list[dict]:
    """Open themes that map to a given canonical theme."""
    rows = conn.execute(
        """SELECT theme_text, COUNT(*) as stock_count,
                  AVG(confidence) as avg_confidence,
                  AVG(distinctiveness) as avg_distinctiveness,
                  AVG(freshness) as avg_freshness,
                  GROUP_CONCAT(DISTINCT ticker) as tickers
           FROM open_themes
           WHERE mapped_canonical = ?
             AND (mapped_similarity IS NULL OR mapped_similarity <= ?)
           GROUP BY theme_text
           ORDER BY stock_count DESC""",
        (canonical_name, config.MAX_MAPPED_SIMILARITY),
    ).fetchall()
    return [dict(r) for r in rows]


def get_narrative_themes(conn: sqlite3.Connection,
                         min_confidence: float = 0.3) -> list[dict]:
    """Aggregated narrative-source open themes."""
    rows = conn.execute(
        """SELECT theme_text, COUNT(*) as stock_count,
                  AVG(confidence) as avg_confidence,
                  AVG(distinctiveness) as avg_distinctiveness,
                  AVG(freshness) as avg_freshness,
                  GROUP_CONCAT(DISTINCT ticker) as tickers
           FROM open_themes
           WHERE source = 'narrative' AND confidence >= ?
           GROUP BY theme_text
           HAVING stock_count >= 2
           ORDER BY stock_count DESC""",
        (min_confidence,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_narrative_heatmap(conn: sqlite3.Connection) -> list[dict]:
    """Narrative themes grouped by mapped canonical category for treemap."""
    rows = conn.execute(
        """SELECT COALESCE(ot.mapped_canonical, 'Uncategorized') as category,
                  ot.theme_text, COUNT(*) as stock_count,
                  AVG(ot.confidence) as avg_confidence,
                  AVG(ot.freshness) as avg_freshness
           FROM open_themes ot
           WHERE ot.source = 'narrative'
           GROUP BY ot.theme_text
           HAVING stock_count >= 2
           ORDER BY stock_count DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_narrative_trend(conn: sqlite3.Connection, days: int = 30) -> list[dict]:
    """Narrative trends: compare current vs previous period counts."""
    rows = conn.execute(
        """SELECT theme_text,
                  COUNT(*) as current_count,
                  AVG(confidence) as avg_confidence,
                  AVG(distinctiveness) as avg_distinctiveness
           FROM open_themes
           WHERE source = 'narrative'
             AND updated_at >= date('now', ?)
           GROUP BY theme_text
           HAVING current_count >= 2
           ORDER BY current_count DESC""",
        (f"-{days} days",),
    ).fetchall()
    return [dict(r) for r in rows]


def get_investor_holdings_for_stock(conn: sqlite3.Connection,
                                     ticker: str) -> list[dict]:
    """13F holdings for a specific stock."""
    rows = conn.execute(
        """SELECT investor_name, investor_short, change_type,
                  shares_current, shares_previous, pct_change, filing_date
           FROM investor_holdings
           WHERE ticker = ?
           ORDER BY filing_date DESC""",
        (ticker.upper(),),
    ).fetchall()
    return [dict(r) for r in rows]


def get_investor_activity(conn: sqlite3.Connection,
                          limit: int = 50) -> list[dict]:
    """Recent 13F activity across all stocks."""
    rows = conn.execute(
        """SELECT ih.ticker, s.name, ih.investor_name, ih.investor_short,
                  ih.change_type, ih.shares_current, ih.shares_previous,
                  ih.pct_change, ih.filing_date
           FROM investor_holdings ih
           LEFT JOIN stocks s ON s.ticker = ih.ticker
           ORDER BY ih.filing_date DESC, ih.updated_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_theme_stock_changes(conn: sqlite3.Connection, theme_name: str,
                            days: int = 30) -> dict:
    """Find stocks added to / removed from a theme over the given period."""
    old_rows = conn.execute(
        """SELECT DISTINCT ticker FROM theme_stock_snapshots
           WHERE theme_name = ? AND snapshot_date = (
               SELECT MIN(snapshot_date) FROM theme_stock_snapshots
               WHERE theme_name = ? AND snapshot_date >= date('now', ?)
           )""",
        (theme_name, theme_name, f"-{days} days"),
    ).fetchall()
    new_rows = conn.execute(
        """SELECT DISTINCT ticker FROM theme_stock_snapshots
           WHERE theme_name = ? AND snapshot_date = (
               SELECT MAX(snapshot_date) FROM theme_stock_snapshots
               WHERE theme_name = ?
           )""",
        (theme_name, theme_name),
    ).fetchall()
    old_set = {r["ticker"] for r in old_rows}
    new_set = {r["ticker"] for r in new_rows}
    return {
        "entrants": sorted(new_set - old_set),
        "exits": sorted(old_set - new_set),
        "period_days": days,
    }


def get_source_breakdown_for_theme(conn: sqlite3.Connection,
                                    theme_name: str) -> dict[str, int]:
    """Count stocks by source type for a canonical theme."""
    rows = conn.execute(
        """SELECT st.source, COUNT(*) as cnt
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           WHERE t.name = ?
           GROUP BY st.source""",
        (theme_name,),
    ).fetchall()
    return {r["source"]: r["cnt"] for r in rows}


def get_emerging_ranked(conn: sqlite3.Connection,
                        min_stock_count: int = 3,
                        limit: int = 20) -> list[dict]:
    """Open themes ranked by composite quality score for the emerging board."""
    w_c = config.QUALITY_WEIGHTS["confidence"]
    w_d = config.QUALITY_WEIGHTS["distinctiveness"]
    rows = conn.execute(
        """SELECT theme_text,
                  COUNT(*) as stock_count,
                  AVG(confidence) as avg_confidence,
                  AVG(distinctiveness) as avg_distinctiveness,
                  AVG(freshness) as avg_freshness,
                  GROUP_CONCAT(DISTINCT ticker) as tickers,
                  mapped_canonical,
                  AVG(mapped_similarity) as avg_mapped_similarity
           FROM open_themes
           WHERE confidence >= 0.4
             AND distinctiveness >= 0.1
             AND (mapped_similarity IS NULL OR mapped_similarity <= ?)
           GROUP BY theme_text
           HAVING stock_count >= ?
           ORDER BY (AVG(confidence) * ? + AVG(distinctiveness) * ?) DESC
           LIMIT ?""",
        (config.MAX_MAPPED_SIMILARITY, min_stock_count, w_c, w_d, limit),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["avg_quality"] = round(
            w_c * d["avg_confidence"] + w_d * d["avg_distinctiveness"], 3
        )
        results.append(d)
    return results


def screener_query(conn: sqlite3.Connection,
                   filters: dict) -> list[dict]:
    """Dynamic multi-filter stock query for the screener."""
    conditions = ["1=1"]
    params: list = []

    if filters.get("themes"):
        placeholders = ",".join("?" for _ in filters["themes"])
        conditions.append(
            f"""s.ticker IN (
                SELECT st.ticker FROM stock_themes st
                JOIN themes t ON t.id = st.theme_id
                WHERE t.name IN ({placeholders})
            )"""
        )
        params.extend(filters["themes"])

    if filters.get("narratives"):
        placeholders = ",".join("?" for _ in filters["narratives"])
        conditions.append(
            f"""s.ticker IN (
                SELECT ot.ticker FROM open_themes ot
                WHERE ot.source = 'narrative'
                  AND ot.theme_text IN ({placeholders})
            )"""
        )
        params.extend(filters["narratives"])

    if filters.get("min_confidence"):
        conditions.append(
            """s.ticker IN (
                SELECT st.ticker FROM stock_themes st
                WHERE st.confidence >= ?
            )"""
        )
        params.append(filters["min_confidence"])

    if filters.get("min_distinctiveness"):
        conditions.append(
            """s.ticker IN (
                SELECT ot.ticker FROM open_themes ot
                WHERE ot.distinctiveness >= ?
            )"""
        )
        params.append(filters["min_distinctiveness"])

    if filters.get("min_freshness"):
        conditions.append(
            """s.ticker IN (
                SELECT ot.ticker FROM open_themes ot
                WHERE ot.freshness >= ?
            )"""
        )
        params.append(filters["min_freshness"])

    if filters.get("sources"):
        placeholders = ",".join("?" for _ in filters["sources"])
        conditions.append(
            f"""s.ticker IN (
                SELECT st.ticker FROM stock_themes st
                WHERE st.source IN ({placeholders})
                UNION
                SELECT ot.ticker FROM open_themes ot
                WHERE ot.source IN ({placeholders})
            )"""
        )
        params.extend(filters["sources"])
        params.extend(filters["sources"])

    if filters.get("sectors"):
        placeholders = ",".join("?" for _ in filters["sectors"])
        conditions.append(f"s.sector IN ({placeholders})")
        params.extend(filters["sectors"])

    if filters.get("min_market_cap"):
        conditions.append("s.market_cap >= ?")
        params.append(filters["min_market_cap"])

    if filters.get("has_13f_activity"):
        conditions.append(
            "s.ticker IN (SELECT ih.ticker FROM investor_holdings ih)"
        )

    if filters.get("near_promotion"):
        conditions.append(
            """s.ticker IN (
                SELECT ot.ticker FROM open_themes ot
                WHERE ot.confidence >= 0.6 AND ot.distinctiveness >= 0.3
            )"""
        )

    where_clause = " AND ".join(conditions)
    sort_col = {
        "market_cap": "s.market_cap",
        "name": "s.name",
    }.get(filters.get("sort_by", "market_cap"), "s.market_cap")
    limit = min(filters.get("limit", 100), 500)

    rows = conn.execute(
        f"""SELECT s.ticker, s.name, s.sector, s.industry, s.market_cap
            FROM stocks s
            WHERE {where_clause}
            ORDER BY {sort_col} DESC NULLS LAST
            LIMIT ?""",
        (*params, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def stats(conn: sqlite3.Connection) -> dict:
    """Return database statistics."""
    stock_count = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    theme_count = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
    assoc_count = conn.execute("SELECT COUNT(*) FROM stock_themes").fetchone()[0]
    msg_count = conn.execute("SELECT COUNT(*) FROM social_messages").fetchone()[0]
    snap_count = conn.execute("SELECT COUNT(*) FROM theme_snapshots").fetchone()[0]
    promo_count = conn.execute("SELECT COUNT(*) FROM promotion_log").fetchone()[0]
    return {
        "stocks": stock_count,
        "themes": theme_count,
        "associations": assoc_count,
        "social_messages": msg_count,
        "snapshots": snap_count,
        "promotions": promo_count,
    }
