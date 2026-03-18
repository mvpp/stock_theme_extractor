"""Taxonomy tree API endpoint."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter

from themes_api import config
from themes_api.db import get_conn, get_theme_distribution

router = APIRouter()


@router.get("/tree")
def taxonomy_tree():
    """Return the full taxonomy hierarchy as nested JSON with stock counts."""
    taxonomy_path = Path(config.TAXONOMY_YAML_PATH)
    if not taxonomy_path.exists():
        return {"tree": {}, "error": "taxonomy.yaml not found"}

    with open(taxonomy_path) as f:
        raw_tree = yaml.safe_load(f) or {}

    conn = get_conn()
    try:
        dist = get_theme_distribution(conn)
    finally:
        conn.close()

    count_map = {d["name"]: d["stock_count"] for d in dist}

    def annotate(node: dict) -> list[dict]:
        result = []
        for name, children in node.items():
            entry = {
                "name": name,
                "stock_count": count_map.get(name, 0),
                "children": annotate(children) if isinstance(children, dict) and children else [],
            }
            result.append(entry)
        return result

    return annotate(raw_tree)
