"""Human-in-the-loop theme promotion service."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

from themes_api import config
from themes_api.db import init_db


def promote_theme(
    db_path: str | Path,
    open_theme_text: str,
    canonical_name: str,
    parent_theme: str | None = None,
    category: str | None = None,
) -> dict:
    """Promote an open theme to canonical."""
    conn = init_db(db_path)

    stats = conn.execute(
        """SELECT COUNT(*) AS stock_count, AVG(confidence) AS avg_confidence
           FROM open_themes WHERE theme_text = ?""",
        (open_theme_text,),
    ).fetchone()

    stock_count = stats["stock_count"] if stats else 0
    avg_confidence = stats["avg_confidence"] if stats else 0.0

    with conn:
        conn.execute(
            """INSERT INTO themes (name, category, description)
               VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET category=excluded.category""",
            (canonical_name, category, f"Promoted from open theme: {open_theme_text}"),
        )

        conn.execute(
            """INSERT INTO promotion_log
                   (open_theme_text, canonical_name, parent_theme, category,
                    stock_count_at_promotion, avg_confidence_at_promotion)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (open_theme_text, canonical_name, parent_theme, category,
             stock_count, avg_confidence),
        )

    if parent_theme:
        _update_taxonomy(canonical_name, parent_theme)

    conn.close()

    return {
        "canonical_name": canonical_name,
        "parent_theme": parent_theme,
        "category": category,
        "stock_count": stock_count,
        "avg_confidence": avg_confidence,
    }


def dismiss_theme(db_path: str | Path, open_theme_text: str) -> dict:
    """Dismiss a promotion candidate."""
    conn = init_db(db_path)
    with conn:
        conn.execute(
            """UPDATE open_themes SET mapped_similarity = 1.0
               WHERE theme_text = ?""",
            (open_theme_text,),
        )
    affected = conn.execute(
        "SELECT changes() AS cnt"
    ).fetchone()["cnt"]
    conn.close()
    return {"dismissed": open_theme_text, "rows_affected": affected}


def get_promotion_history(db_path: str | Path) -> list[dict]:
    """Return the promotion audit log."""
    conn = init_db(db_path)
    rows = conn.execute(
        """SELECT * FROM promotion_log ORDER BY promoted_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _update_taxonomy(canonical_name: str, parent_theme: str):
    """Add the new theme as a child of parent_theme in taxonomy.yaml."""
    taxonomy_path = Path(config.TAXONOMY_YAML_PATH)
    if not taxonomy_path.exists():
        return

    with open(taxonomy_path) as f:
        tree = yaml.safe_load(f) or {}

    if _insert_child(tree, parent_theme, canonical_name):
        with open(taxonomy_path, "w") as f:
            yaml.dump(tree, f, default_flow_style=False, allow_unicode=True)


def _insert_child(node: dict, parent: str, child: str) -> bool:
    """Recursively find parent in the tree and add child as a leaf."""
    for key, children in node.items():
        if key == parent:
            if children is None:
                node[key] = {child: {}}
            elif isinstance(children, dict):
                children[child] = {}
            return True
        if isinstance(children, dict) and _insert_child(children, parent, child):
            return True
    return False
