"""CloudCost Analyzer backend (Shimo agent) - FastAPI application entry point.

Run from the repository root::

    uvicorn backend.main:app --reload

Running ``uvicorn main:app`` from inside ``backend/`` also works.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI  # noqa: E402  pylint: disable=wrong-import-position
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402  pylint: disable=wrong-import-position

from backend.api.routes import router as system_router  # noqa: E402  pylint: disable=wrong-import-position
from backend.api.sessions import router as sessions_router  # noqa: E402  pylint: disable=wrong-import-position
from backend.config import settings  # noqa: E402  pylint: disable=wrong-import-position
from backend.database import init_db  # noqa: E402  pylint: disable=wrong-import-position

logging.basicConfig(
    level=logging.DEBUG if settings.debug else getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shimo")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create tables on startup."""
    init_db()
    logger.info(
        "%s %s ready (llm=%s/%s, db=%s)",
        settings.app_name,
        settings.app_version,
        settings.llm_provider,
        settings.llm_model_name(),
        settings.database_url,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    description=settings.app_tagline,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(sessions_router)


@app.get("/", tags=["system"])
async def root():
    """Service description."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/health",
        "providers": "/api/providers",
        "sessions": "/api/sessions",
    }
