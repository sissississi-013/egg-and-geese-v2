"""Learning Agent — entity-level self-improvement loop.

Periodically analyzes engagement metrics stored in Neo4j, identifies
patterns (which comment styles work, which don't), and adjusts
strategy confidence scores so the swarm evolves over time.

KEY UPGRADE: Uses GLiNER entity-level analysis to understand not just
"which strategies worked" but "which SPECIFIC ENTITIES drove engagement."

This means the system learns things like:
- "Mentioning 'ceramides' got 3x more engagement than 'moisturizing'"
- "Posts responding to 'itchy scalp' pain points had 2x reply rates"
- "Testimonial-style claims outperformed clinical claims on Reddit"
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.models.agent_trace import AgentTrace, AgentType, ActionType
from app.services.claude_service import ClaudeService
from app.services.gliner_service import GLiNERService
from app.services.metrics_service import MetricsService
from app.graph.schemas import (
    update_strategy_confidence,
    create_strategy_node,
)
from app.graph import queries
from app.services.neo4j_service import Neo4jService

logger = logging.getLogger(__name__)


class LearningAgent:
    """Analyzes metrics at entity level, identifies patterns, evolves strategies."""

    @classmethod
    async def run_learning_cycle(
        cls,
        campaign_id: str,
        campaign_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute one learning cycle with entity-level analysis:

        1. Collect latest metrics for all active engagements
        2. Query Neo4j for strategy performance aggregates
        3. Run GLiNER entity extraction on top/bottom performing comments
        4. Ask Claude to analyze patterns WITH entity-level data
        5. Update strategy confidence scores in Neo4j
        6. Identify top-performing entities for future scouting focus

        Returns:
            Dict with insights, entity performance, adjustments, new strategies.
        """
        start = datetime.utcnow()

        # ---- Step 1: Get strategy performance data ----
        performance = await MetricsService.get_strategy_performance(
            campaign_id
        )
        summary = await MetricsService.get_campaign_metrics_summary(
            campaign_id
        )

        if not performance:
            logger.info("LearningAgent: no performance data yet for %s", campaign_id)
            return {
                "insights": ["Not enough data to learn from yet."],
                "adjustments": [],
                "new_strategies": [],
                "entity_insights": {},
                "trace": AgentTrace(
                    campaign_id=campaign_id,
                    agent_type=AgentType.LEARNING,
                    action=ActionType.UPDATE_STRATEGY,
                    input_data={"status": "no_data"},
                    output_data={"skipped": True},
                ).model_dump(),
            }

        # ---- Step 2: Get engagement history for context ----
        history = await Neo4jService.run_query(
            queries.GET_ENGAGEMENT_HISTORY,
            {"campaign_id": campaign_id, "limit": 100},
        )

        # ---- Step 3: GLiNER entity-level analysis ----
        entity_insights = await cls._analyze_entities(
            history, campaign_schema or {}
        )

        # ---- Step 4: Ask Claude to analyze WITH entity data ----
        metrics_text = cls._format_metrics(performance, summary, history)

        # Add entity-level insights to the analysis prompt
        if entity_insights:
            metrics_text += "\n\n=== Entity-Level Performance (from GLiNER) ===\n"
            top_entities = entity_insights.get("top_entities", [])
            for ent in top_entities[:10]:
                metrics_text += (
                    f"- Entity '{ent['text']}' (type: {ent['type']}): "
                    f"avg_likes={ent.get('avg_likes', 0):.1f}, "
                    f"avg_replies={ent.get('avg_replies', 0):.1f}, "
                    f"occurrences={ent.get('count', 0)}\n"
                )
            weak_entities = entity_insights.get("weak_entities", [])
            if weak_entities:
                metrics_text += "\nUnderperforming entities:\n"
                for ent in weak_entities[:5]:
                    metrics_text += (
                        f"- '{ent['text']}' (type: {ent['type']}): "
                        f"avg_likes={ent.get('avg_likes', 0):.1f}\n"
                    )

        analysis = await ClaudeService.analyze_performance(metrics_text)

        # ---- Step 5: Apply confidence adjustments ----
        adjustments_made: list[dict[str, Any]] = []
        confidence_adj = analysis.get("confidence_adjustments", {})

        for strategy_id, new_score in confidence_adj.items():
            if isinstance(new_score, (int, float)):
                clamped = max(0.0, min(1.0, float(new_score)))
                await update_strategy_confidence(strategy_id, clamped)
                adjustments_made.append({
                    "strategy_id": strategy_id,
                    "new_confidence": clamped,
                })

        # ---- Step 6: Create evolved strategies if recommended ----
        new_strategies: list[dict[str, Any]] = []
        recommended = analysis.get("recommended_changes", [])

        top_strat = analysis.get("top_performing_styles", [])
        if top_strat and recommended:
            import uuid

            parent_id = (
                performance[0].get("strategy_id") if performance else None
            )
            for i, change in enumerate(recommended[:3]):
                new_id = uuid.uuid4().hex[:12]
                await create_strategy_node(
                    strategy_id=new_id,
                    style=str(change)[:100],
                    tone="evolved",
                    template_type="adaptive",
                    confidence_score=0.6,
                    parent_strategy_id=parent_id,
                )
                new_strategies.append({
                    "strategy_id": new_id,
                    "description": str(change),
                    "parent": parent_id,
                })

        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        trace = AgentTrace(
            campaign_id=campaign_id,
            agent_type=AgentType.LEARNING,
            action=ActionType.UPDATE_STRATEGY,
            input_data={
                "strategies_analyzed": len(performance),
                "engagements_reviewed": len(history),
                "entities_analyzed": entity_insights.get("total_entities", 0),
            },
            output_data={
                "insights_count": len(analysis.get("insights", [])),
                "adjustments": len(adjustments_made),
                "new_strategies": len(new_strategies),
                "top_entities": len(entity_insights.get("top_entities", [])),
            },
            duration_ms=duration_ms,
        )

        return {
            "insights": analysis.get("insights", []),
            "top_performing": analysis.get("top_performing_styles", []),
            "underperforming": analysis.get("underperforming_styles", []),
            "adjustments": adjustments_made,
            "new_strategies": new_strategies,
            "recommended_changes": recommended,
            "entity_insights": entity_insights,
            "campaign_summary": summary,
            "trace": trace.model_dump(),
        }

    @classmethod
    async def _analyze_entities(
        cls,
        history: list[dict[str, Any]],
        campaign_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Use GLiNER to extract entities from engagement history
        and correlate with performance metrics.

        This is the entity-level learning loop:
        1. For each engagement, extract entities from the comment text
        2. Map each entity to the engagement's performance metrics
        3. Aggregate to find which entities drive the most engagement
        4. Return ranked entity performance data
        """
        if not history:
            return {"top_entities": [], "weak_entities": [], "total_entities": 0}

        # Extract entities from each engagement's comment text
        entity_performance: dict[str, dict[str, Any]] = {}

        for engagement in history[:50]:  # Cap to avoid excessive API calls
            comment = engagement.get("content", "")
            if not comment or len(comment) < 10:
                continue

            metrics = {
                "impressions": engagement.get("impressions", 0),
                "likes": engagement.get("likes", 0),
                "replies": engagement.get("replies", 0),
            }

            try:
                claims = await GLiNERService.extract_claims_from_comment(
                    comment, campaign_schema
                )
                for claim in claims:
                    key = f"{claim['claim_type']}:{claim['text'].lower()}"
                    if key not in entity_performance:
                        entity_performance[key] = {
                            "text": claim["text"],
                            "type": claim["claim_type"],
                            "total_likes": 0,
                            "total_replies": 0,
                            "total_impressions": 0,
                            "count": 0,
                        }
                    ep = entity_performance[key]
                    ep["total_likes"] += metrics["likes"]
                    ep["total_replies"] += metrics["replies"]
                    ep["total_impressions"] += metrics["impressions"]
                    ep["count"] += 1
            except Exception as e:
                logger.debug("Entity extraction failed for engagement: %s", e)

        # Compute averages and rank
        ranked: list[dict[str, Any]] = []
        for key, data in entity_performance.items():
            count = max(1, data["count"])
            ranked.append({
                "text": data["text"],
                "type": data["type"],
                "avg_likes": data["total_likes"] / count,
                "avg_replies": data["total_replies"] / count,
                "avg_impressions": data["total_impressions"] / count,
                "count": data["count"],
                # Composite engagement score
                "engagement_score": (
                    data["total_likes"] / count * 2
                    + data["total_replies"] / count * 3
                    + data["total_impressions"] / count * 0.1
                ),
            })

        # Sort by engagement score
        ranked.sort(key=lambda x: x["engagement_score"], reverse=True)

        return {
            "top_entities": ranked[:15],
            "weak_entities": ranked[-5:] if len(ranked) > 5 else [],
            "total_entities": len(ranked),
        }

    @staticmethod
    def _format_metrics(
        performance: list[dict[str, Any]],
        summary: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> str:
        lines = [
            "=== Campaign Summary ===",
            f"Total engagements: {summary.get('total_engagements', 0)}",
            f"Total impressions: {summary.get('total_impressions', 0)}",
            f"Total likes: {summary.get('total_likes', 0)}",
            f"Total replies: {summary.get('total_replies', 0)}",
            f"Avg sentiment: {summary.get('avg_sentiment', 0):.2f}",
            "",
            "=== Strategy Performance ===",
        ]

        for p in performance:
            lines.append(
                f"Strategy {p.get('strategy_id', '?')} "
                f"(style: {p.get('style', '?')}, tone: {p.get('tone', '?')}): "
                f"avg_imp={p.get('avg_imp', 0):.0f} | "
                f"avg_likes={p.get('avg_likes', 0):.0f} | "
                f"samples={p.get('sample_size', 0)} | "
                f"confidence={p.get('confidence', 0):.2f}"
            )

        lines.append("\n=== Recent Engagements ===")
        for h in history[:30]:
            lines.append(
                f"- [{h.get('action_type', '?')}] "
                f"style={h.get('style', '?')} | "
                f"imp={h.get('impressions', 0)} | "
                f"likes={h.get('likes', 0)} | "
                f"replies={h.get('replies', 0)}"
            )

        return "\n".join(lines)
