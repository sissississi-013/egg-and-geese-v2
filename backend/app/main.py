"""FastAPI application entry point for Egg & Geese v2.

Self-evolving vibe-marketing platform — the orchestrator that ties
together GLiNER, Yutori, Reka Vision, Senso, Claude, OpenClaw, and Neo4j.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.neo4j_service import Neo4jService
from app.orchestrator.scheduler import start_scheduler, stop_scheduler
from app.api import campaigns, agents, metrics, websocket

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("egg_geese")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("Egg & Geese v2 starting up...")

    # Connect Neo4j (non-fatal — app works without it for dev/testing)
    try:
        await Neo4jService.connect()
        await Neo4jService.init_constraints()
        logger.info("Neo4j connected and initialized")
    except Exception as e:
        logger.warning("Neo4j unavailable — running without knowledge graph: %s", e)

    # Start the periodic heartbeat scheduler
    try:
        start_scheduler()
        logger.info("Heartbeat scheduler started")
    except Exception as e:
        logger.warning("Scheduler failed to start: %s", e)

    yield

    # ── Shutdown ──
    try:
        stop_scheduler()
    except Exception:
        pass
    try:
        await Neo4jService.close()
    except Exception:
        pass
    logger.info("Egg & Geese v2 shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Egg & Geese v2",
    description=(
        "Self-evolving multi-agent social media marketing platform. "
        "A swarm of AI agents scout, engage, and learn across "
        "Twitter, Reddit, and Instagram."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS (allow frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3002", "http://localhost:3003", "http://127.0.0.1:3000", "http://127.0.0.1:3002", "http://127.0.0.1:3003"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(campaigns.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {
        "name": "Egg & Geese v2",
        "tagline": "self-evolving vibe-marketing",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "orchestrator"}
