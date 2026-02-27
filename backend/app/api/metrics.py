"""Metrics query and analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.metrics_service import MetricsService
from app.services.neo4j_service import Neo4jService
from app.graph import queries

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/{campaign_id}/summary")
async def campaign_summary(campaign_id: str):
    """Get high-level metrics summary for a campaign."""
    summary = await MetricsService.get_campaign_metrics_summary(campaign_id)
    return summary


@router.get("/{campaign_id}/strategies")
async def strategy_performance(campaign_id: str):
    """Get per-strategy performance breakdown."""
    perf = await MetricsService.get_strategy_performance(campaign_id)
    return {"strategies": perf}


@router.get("/{campaign_id}/history")
async def engagement_history(campaign_id: str, limit: int = 50):
    """Get engagement history with metrics."""
    rows = await Neo4jService.run_query(
        queries.GET_ENGAGEMENT_HISTORY,
        {"campaign_id": campaign_id, "limit": limit},
    )
    return {"history": rows}


@router.get("/{campaign_id}/graph")
async def knowledge_graph(campaign_id: str):
    """Get the full knowledge graph for visualization."""
    rows = await Neo4jService.run_query(
        queries.FULL_GRAPH_OVERVIEW,
        {"campaign_id": campaign_id},
    )

    # Transform Neo4j records into nodes + edges for frontend graph viz
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()

    for row in rows:
        for key in ("c", "p", "pl", "sp", "e", "s", "s2"):
            node = row.get(key)
            if node and isinstance(node, dict):
                node_id = node.get("id") or node.get("name", "")
                if node_id and node_id not in seen_nodes:
                    seen_nodes.add(node_id)
                    # Determine node type from the key
                    type_map = {
                        "c": "Campaign",
                        "p": "Product",
                        "pl": "Platform",
                        "sp": "ScoutedPost",
                        "e": "Engagement",
                        "s": "Strategy",
                        "s2": "Strategy",
                    }
                    nodes.append({
                        "id": node_id,
                        "type": type_map.get(key, "Unknown"),
                        "data": node,
                    })

    return {"nodes": nodes, "edges": edges}
