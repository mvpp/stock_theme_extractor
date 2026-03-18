"""Theme Tradeability Score — 6-component composite score."""

from __future__ import annotations

import sqlite3

from themes_api import config
from themes_api.taxonomy import get_theme_tree


def compute_tradeability(conn: sqlite3.Connection, theme_name: str) -> dict:
    """Compute the tradeability score for a canonical theme.

    Components:
        relevance       — avg confidence from stock_themes
        uniqueness      — avg distinctiveness of mapped open_themes
        recency         — avg freshness of mapped open_themes
        corroboration   — source diversity (distinct sources / total possible)
        narrative_intensity — narrative-source open themes / stock count
        taxonomy_depth  — normalized depth in ThemeTree (leaf=1.0, root=0.2)
    """
    # -- relevance: avg confidence --
    row = conn.execute(
        """SELECT AVG(st.confidence) as avg_conf, COUNT(*) as stock_count
           FROM stock_themes st
           JOIN themes t ON t.id = st.theme_id
           WHERE t.name = ?""",
        (theme_name,),
    ).fetchone()
    avg_conf = row["avg_conf"] or 0.0
    stock_count = row["stock_count"] or 0
    relevance = min(avg_conf, 1.0)

    # -- uniqueness: avg distinctiveness of mapped open themes --
    ot_row = conn.execute(
        """SELECT AVG(distinctiveness) as avg_dist,
                  AVG(freshness) as avg_fresh,
                  COUNT(*) as ot_count
           FROM open_themes
           WHERE mapped_canonical = ?
             AND (mapped_similarity IS NULL OR mapped_similarity <= ?)""",
        (theme_name, config.MAX_MAPPED_SIMILARITY),
    ).fetchone()
    uniqueness = min(ot_row["avg_dist"] or 0.0, 1.0)

    # -- recency: avg freshness --
    recency = min(ot_row["avg_fresh"] or 0.5, 1.0)

    # -- corroboration: distinct sources / total source types --
    sources = conn.execute(
        """SELECT COUNT(DISTINCT source) as src_count
           FROM (
               SELECT st.source FROM stock_themes st
               JOIN themes t ON t.id = st.theme_id
               WHERE t.name = ?
               UNION
               SELECT ot.source FROM open_themes ot
               WHERE ot.mapped_canonical = ?
           )""",
        (theme_name, theme_name),
    ).fetchone()
    corroboration = min(
        (sources["src_count"] or 0) / len(config.ALL_SOURCE_TYPES), 1.0
    )

    # -- narrative_intensity: narrative open themes / stock count --
    narr_row = conn.execute(
        """SELECT COUNT(*) as narr_count
           FROM open_themes
           WHERE mapped_canonical = ? AND source = 'narrative'""",
        (theme_name,),
    ).fetchone()
    narrative_intensity = 0.0
    if stock_count > 0:
        narrative_intensity = min((narr_row["narr_count"] or 0) / stock_count, 1.0)

    # -- taxonomy_depth: depth in theme tree (leaf=1.0, root=0.2) --
    tree = get_theme_tree()
    depth = tree.get_depth(theme_name) if theme_name in tree.themes_in_tree() else 0
    # Normalize: depth 0 → 0.2, depth 1 → 0.4, depth 2 → 0.6, depth 3+ → 1.0
    taxonomy_depth = min(0.2 + depth * 0.27, 1.0)

    # -- composite --
    weights = config.TRADEABILITY_WEIGHTS
    components = {
        "relevance": round(relevance, 3),
        "uniqueness": round(uniqueness, 3),
        "recency": round(recency, 3),
        "corroboration": round(corroboration, 3),
        "narrative_intensity": round(narrative_intensity, 3),
        "taxonomy_depth": round(taxonomy_depth, 3),
    }
    composite = sum(
        components[k] * weights[k] for k in weights
    )

    return {
        "theme_name": theme_name,
        "tradeability_score": round(composite, 3),
        "components": components,
    }
