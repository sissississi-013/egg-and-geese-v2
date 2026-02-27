"""Full agent pipeline — chains all agents in sequence.

Intent -> Scout -> Vision -> Strategy -> Execute -> Metrics

GLiNER is the backbone: every stage uses it for entity extraction.
The campaign_schema (built by GLiNER from the product profile)
flows through the entire pipeline, giving each agent campaign-specific
entity labels for extraction, scoring, and validation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.agents.intent_agent import IntentAgent
from app.agents.scout_agent import ScoutAgent
from app.agents.vision_agent import VisionAgent
from app.agents.strategy_agent import StrategyAgent
from app.services.openclaw_bridge import OpenClawBridge
from app.services.gliner_service import GLiNERService
from app.models.campaign import CampaignCreate
from app.models.metrics import ScoutedPost

logger = logging.getLogger(__name__)


# Type for progress callback
from typing import Callable

ProgressCallback = Callable[[str, str, str, str, dict], None]
"""(agent, action, detail, status, meta)"""


def _noop_progress(agent: str, action: str, detail: str = "", status: str = "running", meta: dict | None = None):
    """Default no-op progress callback."""
    pass


class AgentPipeline:
    """Orchestrates the complete agent pipeline for a campaign cycle.

    The pipeline flows a campaign_schema (built by GLiNER) through
    every stage, so each agent uses campaign-specific entity labels.
    """

    @classmethod
    async def run_full_cycle(
        cls,
        campaign_data: CampaignCreate | None = None,
        campaign_id: str | None = None,
        product_id: str | None = None,
        pain_points: list[str] | None = None,
        platforms: list[str] | None = None,
        expected_visual_context: str | None = None,
        campaign_schema: dict[str, Any] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Run the complete pipeline from onboarding to execution.

        For new campaigns, pass campaign_data.
        For existing campaigns, pass campaign_id + product_id + pain_points.

        The campaign_schema is built by GLiNER during intent extraction
        and passed through to scouting, validation, and learning.

        Returns:
            Full pipeline result with all traces and stats.
        """
        emit = on_progress or _noop_progress

        start = datetime.utcnow()
        traces: list[dict] = []
        result: dict[str, Any] = {"status": "running", "traces": traces}

        # ---- Phase 1: Intent Extraction (for new campaigns) ----
        if campaign_data:
            logger.info("Pipeline: Phase 1 — Intent Extraction (GLiNER + Senso)")
            emit("intent", "extracting", "Analyzing product description with GLiNER NER", "running")
            emit("intent", "gliner_call", "Running zero-shot entity extraction (Fastino API)", "running")
            intent_result = await IntentAgent.process(campaign_data)
            traces.append(intent_result["trace"])

            campaign_id = intent_result["campaign_id"]
            product_id = intent_result["product_id"]
            pain_points = intent_result["extracted_entities"].get(
                "pain_points", []
            )
            platforms = campaign_data.platforms
            expected_visual_context = ", ".join(pain_points) if pain_points else None

            # Build campaign-specific entity schema from GLiNER extractions
            campaign_schema = GLiNERService.build_campaign_schema({
                "product_name": intent_result["extracted_entities"].get("product_name", ""),
                "category": intent_result["extracted_entities"].get("category", ""),
                "pain_points": pain_points,
                "benefits": intent_result["extracted_entities"].get("benefits", []),
                "ingredients": intent_result["extracted_entities"].get("ingredients", []),
                "grouped": {},
            })

            result["intent"] = {
                "campaign_id": campaign_id,
                "product_id": product_id,
                "extracted_entities": intent_result["extracted_entities"],
                "campaign_schema": campaign_schema,
            }

            n_pain = len(pain_points or [])
            n_benefits = len(intent_result["extracted_entities"].get("benefits", []))
            n_features = len(intent_result["extracted_entities"].get("key_features", []))
            emit("intent", "entities_extracted",
                 f"Found {n_pain} pain points, {n_benefits} benefits, {n_features} features",
                 "done",
                 {"pain_points": n_pain, "benefits": n_benefits, "features": n_features})
            if campaign_schema:
                n_labels = len(campaign_schema.get("scouting_labels", []))
                emit("intent", "schema_built",
                     f"Generated campaign schema with {n_labels} scouting labels",
                     "done",
                     {"scouting_labels": n_labels})
            emit("intent", "completed", "Intent extraction complete", "done")

        if not campaign_id or not product_id:
            raise ValueError("campaign_id and product_id are required")

        pain_points = pain_points or []
        platforms = platforms or ["twitter", "reddit", "instagram"]

        # Build schema from pain points if not already built
        if not campaign_schema:
            campaign_schema = GLiNERService.build_campaign_schema({
                "pain_points": pain_points,
                "benefits": [],
                "ingredients": [],
                "category": "",
            })

        # ---- Phase 2: Scouting (GLiNER entity-driven scoring) ----
        logger.info("Pipeline: Phase 2 — Scouting across %s (entity-driven)", platforms)
        emit("scout", "yutori_call", f"Querying Yutori Scouts API across {', '.join(platforms or [])}", "running")
        scout_result = await ScoutAgent.scout(
            campaign_id=campaign_id,
            product_id=product_id,
            pain_points=pain_points,
            platforms=platforms,
            campaign_schema=campaign_schema,
        )
        traces.append(scout_result["trace"])
        result["scouting"] = scout_result["stats"]

        total_found = scout_result["stats"].get("total_found", 0)
        total_relevant = scout_result["stats"].get("total_relevant", total_found)
        emit("scout", "scoring", f"GLiNER entity-overlap scoring on {total_found} posts", "running")
        emit("scout", "completed",
             f"Found {total_relevant} relevant posts out of {total_found} total",
             "done",
             {"total": total_found, "relevant": total_relevant})

        scouted_posts = [
            ScoutedPost(**p) for p in scout_result["posts"]
        ]

        if not scouted_posts:
            result["status"] = "completed_no_posts"
            result["message"] = "No relevant posts found in this cycle."
            return result

        # ---- Phase 3: Visual Analysis ----
        logger.info("Pipeline: Phase 3 — Visual Scout (Reka Vision)")
        emit("vision", "reka_call", f"Sending {len(scouted_posts)} post images to Reka Vision API", "running")
        vision_result = await VisionAgent.analyze_posts(
            campaign_id=campaign_id,
            posts=scouted_posts,
            expected_context=expected_visual_context or ", ".join(pain_points),
        )
        traces.append(vision_result["trace"])
        result["vision"] = vision_result["stats"]

        analyzed = vision_result["stats"].get("analyzed", 0)
        emit("vision", "completed",
             f"Analyzed {analyzed} post images for visual context",
             "done",
             {"analyzed": analyzed})

        enriched_posts = vision_result["enriched_posts"]

        # ---- Phase 4: Strategy & Comment Generation ----
        logger.info("Pipeline: Phase 4 — Strategy (Claude + Senso)")
        emit("strategy", "claude_call", "Claude drafting humanized engagement comments", "running")
        campaign_context = (
            f"Product: {result.get('intent', {}).get('extracted_entities', {}).get('product_name', 'Unknown')}\n"
            f"Pain points: {', '.join(pain_points)}\n"
            f"Platforms: {', '.join(platforms)}"
        )

        strategy_result = await StrategyAgent.plan_engagements(
            campaign_id=campaign_id,
            product_id=product_id,
            enriched_posts=enriched_posts,
            campaign_context=campaign_context,
        )
        traces.append(strategy_result["trace"])
        planned = len(strategy_result["engagements"])
        result["strategy"] = {
            "strategy_id": strategy_result["strategy_id"],
            "planned_engagements": planned,
            "reasoning": strategy_result["reasoning"],
        }

        emit("strategy", "senso_validate", "Validating product claims via Senso API", "running")
        emit("strategy", "gliner_claims", "GLiNER extracting structured claims from drafts", "running")
        emit("strategy", "completed",
             f"Planned {planned} engagements with validated comments",
             "done",
             {"planned": planned, "reasoning": strategy_result["reasoning"][:100]})

        # ---- Phase 5: Execution via OpenClaw ----
        logger.info("Pipeline: Phase 5 — Execution (OpenClaw Gateway)")
        emit("engagement", "openclaw_call", f"Dispatching {planned} engagements via OpenClaw", "running")
        executed: list[dict[str, Any]] = []

        for eng in strategy_result["engagements"]:
            try:
                if eng["action_type"] == "comment":
                    exec_result = await OpenClawBridge.post_comment(
                        platform=eng["platform"],
                        post_url=eng["post_url"],
                        comment_text=eng["content"],
                        metadata={
                            "campaign_id": campaign_id,
                            "engagement_id": eng["engagement_id"],
                            "strategy_id": eng["strategy_id"],
                        },
                    )
                elif eng["action_type"] == "reply":
                    exec_result = await OpenClawBridge.post_reply(
                        platform=eng["platform"],
                        post_url=eng["post_url"],
                        parent_comment_id=eng.get("parent_comment_id", ""),
                        reply_text=eng["content"],
                    )
                elif eng["action_type"] == "repost":
                    exec_result = await OpenClawBridge.repost(
                        platform=eng["platform"],
                        post_url=eng["post_url"],
                        quote_text=eng["content"],
                    )
                else:
                    continue

                executed.append({
                    "engagement_id": eng["engagement_id"],
                    "platform": eng["platform"],
                    "action": eng["action_type"],
                    "status": "success",
                    "platform_id": exec_result.get("platform_post_id"),
                })
            except Exception as e:
                logger.error(
                    "Execution failed for engagement %s: %s",
                    eng["engagement_id"],
                    e,
                )
                executed.append({
                    "engagement_id": eng["engagement_id"],
                    "platform": eng["platform"],
                    "action": eng["action_type"],
                    "status": "failed",
                    "error": str(e),
                })

        result["execution"] = {
            "total": len(executed),
            "successful": sum(1 for e in executed if e["status"] == "success"),
            "failed": sum(1 for e in executed if e["status"] == "failed"),
            "details": executed,
        }

        success_count = sum(1 for e in executed if e["status"] == "success")
        failed_count = sum(1 for e in executed if e["status"] == "failed")

        # Emit per-execution events (first 5)
        for detail in executed[:5]:
            emit("engagement", "posted",
                 f"{detail['action']} on {detail['platform']} — {detail['status']}",
                 "done" if detail["status"] == "success" else "error",
                 detail)

        emit("engagement", "completed",
             f"Executed {success_count}/{len(executed)} engagements ({failed_count} failed)",
             "done",
             {"total": len(executed), "success": success_count, "failed": failed_count})

        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        result["status"] = "completed"
        result["total_duration_ms"] = duration_ms
        result["traces"] = traces

        emit("coordinator", "pipeline_complete",
             f"Pipeline finished in {duration_ms}ms",
             "done",
             {"duration_ms": duration_ms})

        logger.info(
            "Pipeline complete: %d engagements executed in %dms",
            len(executed),
            duration_ms,
        )

        return result
