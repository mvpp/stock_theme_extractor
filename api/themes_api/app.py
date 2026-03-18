"""FastAPI application factory — standalone API, no static file serving."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from themes_api.routers import (
    themes,
    stocks,
    search,
    promotions,
    taxonomy,
    admin,
    discover,
    narratives,
    screener,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stock Themes API",
        description="REST API for stock themes analytics — regime classification, drift detection, and theme ranking",
        version="0.1.0",
    )

    allowed_origins = os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173"
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(themes.router, prefix="/api/v1/themes", tags=["themes"])
    app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["stocks"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(promotions.router, prefix="/api/v1/promotions", tags=["promotions"])
    app.include_router(taxonomy.router, prefix="/api/v1/taxonomy", tags=["taxonomy"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    app.include_router(discover.router, prefix="/api/v1", tags=["discover"])
    app.include_router(narratives.router, prefix="/api/v1", tags=["narratives"])
    app.include_router(screener.router, prefix="/api/v1", tags=["screener"])

    return app


app = create_app()
