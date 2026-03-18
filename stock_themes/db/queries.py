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


def get_all_themes(ticker: str, db_path: str = "stock_themes.db",
                   min_confidence: float = 0.0) -> list[dict]:
    """Return canonical + quality-filtered open themes for a ticker.

    Each dict has keys: name, confidence, source, evidence, tier.
    Open themes additionally have: distinctiveness, quality_score,
    mapped_canonical, mapped_similarity.

    Quality filtering uses a composite score:
        quality = w_conf * confidence + w_dist * distinctiveness
    with source-specific thresholds (LLM vs narrative).
    Open themes that nearly duplicate a canonical theme are suppressed.
    """
    from stock_themes.config import (
        UNIFIED_QUALITY_WEIGHTS, UNIFIED_THRESHOLDS, UNIFIED_MAX_MAPPED_SIM,
    )

    store = ThemeStore(db_path)
    try:
        # 1. Canonical themes
        canonical = store.get_themes_for_stock(ticker, min_confidence)
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

        # 2. Quality-filtered open themes
        # Use the lowest floor across sources for the SQL query;
        # apply source-specific thresholds in Python
        min_conf_floor = min(
            UNIFIED_THRESHOLDS["llm"]["min_confidence"],
            UNIFIED_THRESHOLDS["narrative"]["min_confidence"],
        )
        min_dist_floor = min(
            UNIFIED_THRESHOLDS["llm"]["min_distinctiveness"],
            UNIFIED_THRESHOLDS["narrative"]["min_distinctiveness"],
        )
        open_rows = store.get_filtered_open_themes(
            ticker,
            min_confidence=min_conf_floor,
            min_distinctiveness=min_dist_floor,
            max_mapped_similarity=UNIFIED_MAX_MAPPED_SIM,
        )

        w_conf = UNIFIED_QUALITY_WEIGHTS["confidence"]
        w_dist = UNIFIED_QUALITY_WEIGHTS["distinctiveness"]

        for ot in open_rows:
            # Source-specific thresholds
            src = ot["source"]
            thresh = UNIFIED_THRESHOLDS.get(src, UNIFIED_THRESHOLDS["llm"])

            if ot["confidence"] < thresh["min_confidence"]:
                continue
            if ot["distinctiveness"] < thresh["min_distinctiveness"]:
                continue

            quality = w_conf * ot["confidence"] + w_dist * ot["distinctiveness"]
            if quality < thresh["min_quality"]:
                continue

            # Suppress if it duplicates a canonical theme
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
    finally:
        store.close()


def find_stocks(theme_name: str, db_path: str = "stock_themes.db",
                min_confidence: float = 0.3,
                include_descendants: bool = True,
                fallback_open: bool = True) -> list[dict]:
    """Find all stocks matching a theme, optionally including descendants.

    When include_descendants=True (default), searching for "artificial intelligence"
    also returns stocks tagged with "generative ai", "machine learning", etc.

    When fallback_open=True (default) and canonical search returns no results,
    falls back to searching open_themes via text matching with quality filters.
    """
    store = ThemeStore(db_path)
    try:
        # 1. Canonical search (with taxonomy expansion)
        results: list[dict] = []
        if include_descendants:
            from stock_themes.taxonomy.tree import get_theme_tree
            tree = get_theme_tree()
            descendants = tree.get_descendants(theme_name)
            if descendants:
                all_names = [theme_name] + descendants
                results = store.get_stocks_for_themes(all_names, min_confidence)

        if not results:
            results = store.get_stocks_for_theme(theme_name, min_confidence)

        # 2. Semantic bridging: fall back to open_themes
        if not results and fallback_open:
            from stock_themes.config import (
                UNIFIED_THRESHOLDS, UNIFIED_MAX_MAPPED_SIM,
            )
            thresh = UNIFIED_THRESHOLDS["llm"]
            open_results = store.search_open_themes(
                theme_name,
                min_confidence=thresh["min_confidence"],
                min_distinctiveness=thresh["min_distinctiveness"],
                max_mapped_similarity=UNIFIED_MAX_MAPPED_SIM,
            )
            for r in open_results:
                r["tier"] = "open"
                r["theme_name"] = r.pop("theme_text", theme_name)
            results = open_results

        return results
    finally:
        store.close()


def suggest_promotions(db_path: str = "stock_themes.db") -> list[dict]:
    """Identify open themes ready for promotion to canonical.

    Returns themes appearing in N+ stocks with high avg confidence
    and distinctiveness. Each dict includes theme_text, stock_count,
    avg_confidence, avg_distinctiveness, tickers, and nearest
    mapped_canonical (for suggested placement in taxonomy).

    This is a suggestion list for human review — no auto-promotion.
    """
    from stock_themes.config import UNIFIED_PROMOTION, UNIFIED_QUALITY_WEIGHTS

    store = ThemeStore(db_path)
    try:
        candidates = store.get_promotion_candidates(
            min_stock_count=UNIFIED_PROMOTION["min_stock_count"],
            min_avg_confidence=UNIFIED_PROMOTION["min_avg_confidence"],
            min_avg_distinctiveness=UNIFIED_PROMOTION["min_avg_distinctiveness"],
        )

        w_c = UNIFIED_QUALITY_WEIGHTS["confidence"]
        w_d = UNIFIED_QUALITY_WEIGHTS["distinctiveness"]

        results = []
        for c in candidates:
            avg_quality = w_c * c["avg_confidence"] + w_d * c["avg_distinctiveness"]
            if avg_quality < UNIFIED_PROMOTION["min_avg_quality"]:
                continue
            c["avg_quality"] = round(avg_quality, 3)
            results.append(c)
        return results
    finally:
        store.close()


def get_investor_themes(ticker: str, db_path: str = "stock_themes.db") -> list[dict]:
    """Get 13F-sourced themes for a ticker."""
    store = ThemeStore(db_path)
    try:
        all_open = store.get_open_themes(ticker)
        return [t for t in all_open if t.get("source") == "13f"]
    finally:
        store.close()


def get_stocks_with_investor_activity(
    investor_short: str, db_path: str = "stock_themes.db",
) -> list[dict]:
    """Find all stocks where a specific investor has 13F activity.

    Args:
        investor_short: Short name (e.g., "buffett", "ark"). Case-insensitive.
    """
    store = ThemeStore(db_path)
    try:
        return store.search_open_themes(
            investor_short.lower(),
            min_confidence=0.0,
            min_distinctiveness=0.0,
            max_mapped_similarity=1.0,
        )
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
