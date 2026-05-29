"""Cloud Analytics — FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.api.routes import router
    from backend.api.sessions import router as sessions_router
    from backend.config import settings
    from backend.database import init_db
except ImportError:
    from api.routes import router
    from api.sessions import router as sessions_router
    from config import settings
    from database import init_db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Initialize database
init_db()

app = FastAPI(
    title=settings.app_name,
    description="Shimo - Multi-Cloud Cost Analytics using AI Agents",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(sessions_router)


@app.get("/")
async def root():
    """Root endpoint redirect info."""
    return {
        "service": settings.app_name,
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "sessions": "/api/sessions",
    }
