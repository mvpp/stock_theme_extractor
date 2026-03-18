"""Stock screener endpoint — multi-filter stock search."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from themes_api.db import get_conn
from themes_api.services.screener import run_screener

router = APIRouter()


class ScreenerFilter(BaseModel):
    themes: list[str] = []
    narratives: list[str] = []
    min_confidence: float | None = None
    min_distinctiveness: float | None = None
    min_freshness: float | None = None
    sources: list[str] = []
    sectors: list[str] = []
    min_market_cap: float | None = None
    has_13f_activity: bool = False
    near_promotion: bool = False
    sort_by: str = "market_cap"
    limit: int = 100


@router.post("/screener")
def screener(filters: ScreenerFilter):
    """Multi-filter stock screener."""
    conn = get_conn()
    try:
        return run_screener(conn, filters.model_dump(exclude_none=True))
    finally:
        conn.close()
