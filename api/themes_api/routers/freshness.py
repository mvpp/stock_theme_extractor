"""Data freshness endpoint — reports pipeline run status."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter

from themes_api import config
from themes_api.db import init_db

router = APIRouter()

STALE_HOURS = 36  # accounts for weekends (Fri 4pm to Mon 4am = ~36h)
PIPELINE_NAMES = ["price_pipeline", "snapshot_pipeline", "regime_pipeline"]


@router.get("/data-freshness")
def data_freshness():
    conn = init_db(config.DB_PATH)
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=STALE_HOURS)

    results = []
    for name in PIPELINE_NAMES:
        row = conn.execute(
            """SELECT run_date, status, tickers_processed, tickers_failed,
                      completed_at
               FROM pipeline_runs
               WHERE pipeline_name = ?
               ORDER BY completed_at DESC LIMIT 1""",
            (name,),
        ).fetchone()

        if row:
            last_run = row["completed_at"]
            is_stale = True
            if last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run)
                    is_stale = last_dt < stale_cutoff
                except (ValueError, TypeError):
                    pass

            results.append({
                "pipeline_name": name,
                "last_run": last_run,
                "status": row["status"],
                "tickers_processed": row["tickers_processed"],
                "tickers_failed": row["tickers_failed"],
                "is_stale": is_stale,
            })
        else:
            results.append({
                "pipeline_name": name,
                "last_run": None,
                "status": None,
                "tickers_processed": None,
                "tickers_failed": None,
                "is_stale": True,
            })

    conn.close()
    return results
