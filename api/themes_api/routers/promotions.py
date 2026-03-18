"""Promotion API endpoints — human-in-the-loop theme management."""

from __future__ import annotations

from fastapi import APIRouter

from themes_api import config
from themes_api.db import get_conn, suggest_promotions
from themes_api.response_models import PromoteRequest, DismissRequest
from themes_api.services.promotion import (
    promote_theme, dismiss_theme, get_promotion_history,
)

router = APIRouter()


@router.get("/candidates")
def list_candidates():
    conn = get_conn()
    try:
        candidates = suggest_promotions(conn)
        # Enrich with representative tickers and recommended taxonomy branch
        from themes_api.taxonomy import get_theme_tree
        tree = get_theme_tree()
        for c in candidates:
            tickers_str = c.get("tickers", "")
            tickers_list = [t.strip() for t in tickers_str.split(",") if t.strip()]
            c["representative_tickers"] = tickers_list[:5]
            mapped = c.get("mapped_canonical")
            if mapped and mapped in tree.themes_in_tree():
                ancestors = tree.get_ancestors(mapped)
                c["recommended_branch"] = (
                    " → ".join(reversed(ancestors)) + f" → {mapped}"
                    if ancestors else mapped
                )
            else:
                c["recommended_branch"] = None
        return candidates
    finally:
        conn.close()


@router.post("/promote")
def promote(req: PromoteRequest):
    return promote_theme(
        db_path=config.DB_PATH,
        open_theme_text=req.open_theme_text,
        canonical_name=req.canonical_name,
        parent_theme=req.parent_theme,
        category=req.category,
    )


@router.post("/dismiss")
def dismiss(req: DismissRequest):
    return dismiss_theme(config.DB_PATH, req.open_theme_text)


@router.get("/history")
def promotion_history():
    return get_promotion_history(config.DB_PATH)
