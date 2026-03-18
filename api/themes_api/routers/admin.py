"""Admin and stats endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from themes_api import config
from themes_api.db import get_conn, stats
from themes_api.services.snapshot import take_snapshot

router = APIRouter()


@router.get("/stats")
def get_stats():
    conn = get_conn()
    try:
        return stats(conn)
    finally:
        conn.close()


@router.post("/snapshots/take")
def trigger_snapshot(snapshot_date: str | None = None):
    """Manually trigger a theme snapshot."""
    return take_snapshot(config.DB_PATH, snapshot_date)
