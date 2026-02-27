"""Swarm Coordinator — manages multiple concurrent campaign pipelines.

Handles campaign lifecycle, parallel execution across campaigns,
and coordinates the learning loop feedback.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from typing import Callable

from app.models.campaign import CampaignCreate, CampaignStatus
from app.orchestrator.pipeline import AgentPipeline, ProgressCallback
from app.agents.learning_agent import LearningAgent
from app.services.metrics_service import MetricsService
from app.services.neo4j_service import Neo4jService

logger = logging.getLogger(__name__)


# In-memory campaign state (would be Redis in production)
_active_campaigns: dict[str, dict[str, Any]] = {}


class SwarmCoordinator:
    """Manages the full swarm of agents across all active campaigns."""

    @classmethod
    async def launch_campaign(
        cls,
        campaign_data: CampaignCreate,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Initialize and run the first pipeline cycle for a new campaign.

        Returns:
            First-cycle results including campaign_id.
        """
        logger.info("SwarmCoordinator: launching new campaign '%s'", campaign_data.name)

        result = await AgentPipeline.run_full_cycle(
            campaign_data=campaign_data,
            on_progress=on_progress,
        )

        campaign_id = result.get("intent", {}).get("campaign_id", "")
        product_id = result.get("intent", {}).get("product_id", "")

        # Track active campaign (including GLiNER campaign schema)
        _active_campaigns[campaign_id] = {
            "campaign_id": campaign_id,
            "product_id": product_id,
            "name": campaign_data.name,
            "platforms": campaign_data.platforms,
            "pain_points": (
                result.get("intent", {})
                .get("extracted_entities", {})
                .get("pain_points", [])
            ),
            "campaign_schema": result.get("intent", {}).get("campaign_schema", {}),
            "status": CampaignStatus.ACTIVE,
            "cycles_completed": 1,
            "last_cycle_result": result,
        }

        return result

    @classmethod
    async def run_cycle(
        cls,
        campaign_id: str,
    ) -> dict[str, Any]:
        """Run a single pipeline cycle for an existing campaign.

        This is called by the scheduler on each heartbeat.
        """
        state = _active_campaigns.get(campaign_id)
        if not state:
            raise ValueError(f"Campaign {campaign_id} not found in active swarm")

        if state["status"] != CampaignStatus.ACTIVE:
            return {"status": "skipped", "reason": f"Campaign is {state['status']}"}

        logger.info("SwarmCoordinator: running cycle %d for campaign %s",
                     state["cycles_completed"] + 1, campaign_id)

        result = await AgentPipeline.run_full_cycle(
            campaign_id=campaign_id,
            product_id=state["product_id"],
            pain_points=state["pain_points"],
            platforms=state["platforms"],
            campaign_schema=state.get("campaign_schema"),
        )

        state["cycles_completed"] += 1
        state["last_cycle_result"] = result

        return result

    @classmethod
    async def run_learning(cls, campaign_id: str) -> dict[str, Any]:
        """Trigger a learning cycle for a campaign."""
        logger.info("SwarmCoordinator: learning cycle for campaign %s", campaign_id)
        return await LearningAgent.run_learning_cycle(campaign_id)

    @classmethod
    async def run_metrics_collection(
        cls,
        campaign_id: str,
    ) -> dict[str, Any]:
        """Collect metrics for all active engagements in a campaign."""
        # Get all engagement IDs from Neo4j
        rows = await Neo4jService.run_query(
            """
            MATCH (c:Campaign {id: $cid})-[:TARGETS]->(:Product)
                  <-[:DISCUSSES]-(sp:ScoutedPost)<-[:ON_POST]-(e:Engagement)
            RETURN e.id AS engagement_id, sp.platform AS platform
            """,
            {"cid": campaign_id},
        )

        # Group by platform
        by_platform: dict[str, list[str]] = {}
        for row in rows:
            platform = row.get("platform", "unknown")
            by_platform.setdefault(platform, []).append(
                row.get("engagement_id", "")
            )

        all_metrics = []
        for platform, ids in by_platform.items():
            try:
                metrics = await MetricsService.collect_and_store(
                    campaign_id, platform, ids
                )
                all_metrics.extend([m.model_dump() for m in metrics])
            except Exception as e:
                logger.error("Metrics collection failed for %s: %s", platform, e)

        return {
            "collected": len(all_metrics),
            "by_platform": {k: len(v) for k, v in by_platform.items()},
        }

    @classmethod
    async def run_full_heartbeat(cls) -> dict[str, Any]:
        """Run a complete heartbeat across ALL active campaigns.

        Called by the scheduler every N minutes. For each active campaign:
        1. Collect metrics
        2. Run learning cycle
        3. Run new engagement cycle
        """
        results: dict[str, Any] = {}

        for cid, state in _active_campaigns.items():
            if state["status"] != CampaignStatus.ACTIVE:
                continue

            try:
                metrics = await cls.run_metrics_collection(cid)
                learning = await cls.run_learning(cid)
                cycle = await cls.run_cycle(cid)

                results[cid] = {
                    "metrics": metrics,
                    "learning": learning.get("insights", []),
                    "cycle": cycle.get("status"),
                }
            except Exception as e:
                logger.error("Heartbeat failed for campaign %s: %s", cid, e)
                results[cid] = {"error": str(e)}

        return results

    @classmethod
    def get_active_campaigns(cls) -> list[dict[str, Any]]:
        """List all active campaigns and their state."""
        return [
            {
                "campaign_id": state["campaign_id"],
                "name": state["name"],
                "status": state["status"],
                "cycles_completed": state["cycles_completed"],
                "platforms": state["platforms"],
            }
            for state in _active_campaigns.values()
        ]

    @classmethod
    def pause_campaign(cls, campaign_id: str) -> bool:
        if campaign_id in _active_campaigns:
            _active_campaigns[campaign_id]["status"] = CampaignStatus.PAUSED
            return True
        return False

    @classmethod
    def resume_campaign(cls, campaign_id: str) -> bool:
        if campaign_id in _active_campaigns:
            _active_campaigns[campaign_id]["status"] = CampaignStatus.ACTIVE
            return True
        return False
