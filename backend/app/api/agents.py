"""Agent control and trace query endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.neo4j_service import Neo4jService
from app.graph import queries
from app.services.openclaw_bridge import OpenClawBridge

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/activity")
async def get_activity(limit: int = 50):
    """Get recent agent activity across all campaigns."""
    rows = await Neo4jService.run_query(
        queries.RECENT_ACTIVITY,
        {"limit": limit},
    )
    return {"activity": rows}


@router.get("/strategies")
async def get_top_strategies(min_usage: int = 1, limit: int = 10):
    """Get top-performing strategies."""
    rows = await Neo4jService.run_query(
        queries.TOP_STRATEGIES,
        {"min_usage": min_usage, "limit": limit},
    )
    return {"strategies": rows}


@router.get("/strategies/{strategy_id}/evolution")
async def get_strategy_evolution(strategy_id: str):
    """Get the evolution chain of a strategy."""
    rows = await Neo4jService.run_query(
        queries.STRATEGY_EVOLUTION_CHAIN,
        {"strategy_id": strategy_id},
    )
    return {"evolution": rows}


@router.get("/health")
async def gateway_health():
    """Check OpenClaw gateway health."""
    healthy = await OpenClawBridge.health_check()
    return {
        "gateway": "healthy" if healthy else "unreachable",
        "status": "ok" if healthy else "degraded",
    }
