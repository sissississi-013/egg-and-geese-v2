"""Strategy Agent — powered by Claude (Anthropic).

The brain of the swarm. Takes all context (post, visual analysis,
product info, historical performance data) and decides:
- Which posts to engage with
- What type of engagement (comment, reply, repost)
- What tone and style to use
- Whether to try experimental new approaches

Then generates the actual humanized comment text.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Any

from app.models.agent_trace import AgentTrace, AgentType, ActionType
from app.services.claude_service import ClaudeService
from app.agents.product_agent import ProductAgent
from app.graph.schemas import create_strategy_node, create_engagement_node
from app.graph import queries
from app.services.neo4j_service import Neo4jService

logger = logging.getLogger(__name__)


class StrategyAgent:
    """Decides engagement strategy and generates humanized comments."""

    @classmethod
    async def plan_engagements(
        cls,
        campaign_id: str,
        product_id: str,
        enriched_posts: list[dict[str, Any]],
        campaign_context: str,
    ) -> dict[str, Any]:
        """Create an engagement plan for discovered posts.

        1. Fetch historical performance from Neo4j
        2. Ask Claude to create a strategy
        3. Generate comments for each selected post
        4. Validate via ProductAgent
        5. Store strategy and engagement nodes in Neo4j

        Returns:
            Dict with planned engagements ready for execution.
        """
        start = datetime.utcnow()

        # Fetch historical performance
        history = await Neo4jService.run_query(
            queries.GET_ENGAGEMENT_HISTORY,
            {"campaign_id": campaign_id, "limit": 50},
        )

        top_strategies = await Neo4jService.run_query(
            queries.TOP_STRATEGIES,
            {"min_usage": 1, "limit": 5},
        )

        history_text = cls._format_history(history, top_strategies)

        # Format available posts for Claude
        posts_text = cls._format_posts(enriched_posts)

        # Ask Claude for strategy
        strategy_plan = await ClaudeService.generate_strategy(
            campaign_context=campaign_context,
            historical_performance=history_text,
            available_posts=posts_text,
        )

        strategy_id = strategy_plan.get(
            "strategy_id", uuid.uuid4().hex[:12]
        )

        # Create strategy node in Neo4j
        await create_strategy_node(
            strategy_id=strategy_id,
            style=strategy_plan.get("reasoning", "adaptive")[:100],
            tone="casual_authentic",
            template_type="contextual",
            confidence_score=0.5,
        )

        # Generate comments for each planned action
        engagements: list[dict[str, Any]] = []
        actions = strategy_plan.get("actions", [])

        for action in actions:
            post_id = action.get("post_id", "")
            # Find the matching post
            post = next(
                (p for p in enriched_posts if p.get("id") == post_id),
                None,
            )
            if not post:
                continue

            # Get product context from Senso
            product_context = await ProductAgent.get_product_context(
                product_id, post.get("text", "")
            )

            # Build visual context string
            visual_ctx = ""
            if post.get("visual_analysis") and post.get("visual_match"):
                va = post["visual_analysis"]
                visual_ctx = va.get("visual_summary", "")

            # Generate humanized comment
            comment = await ClaudeService.generate_comment(
                post_context=(
                    f"Platform: {post.get('platform', 'unknown')}\n"
                    f"Post text: {post.get('text', '')}\n"
                    f"Author: {post.get('author', 'anonymous')}"
                ),
                product_info=product_context,
                visual_context=visual_ctx or None,
                strategy_hints="\n".join(
                    action.get("key_points", [])
                ),
                tone=action.get("tone", "casual and authentic"),
            )

            # Validate comment accuracy using GLiNER claim extraction + Senso
            validation = await ProductAgent.validate_comment(
                product_id, comment
            )

            if not validation["valid"]:
                logger.warning(
                    "Comment failed GLiNER claim validation for post %s: %s",
                    post_id,
                    validation["issues"],
                )
                # Regenerate with corrections — include GLiNER's claim analysis
                issues_text = "\n".join(validation["issues"])
                comment = await ClaudeService.generate_comment(
                    post_context=(
                        f"Platform: {post.get('platform', 'unknown')}\n"
                        f"Post text: {post.get('text', '')}\n"
                        f"IMPORTANT: The following claims were flagged as "
                        f"unsupported — avoid them:\n{issues_text}"
                    ),
                    product_info=product_context,
                    visual_context=visual_ctx or None,
                    tone=action.get("tone", "casual and authentic"),
                )

            engagement_id = uuid.uuid4().hex
            action_type = action.get("action_type", "comment")

            # Store engagement in Neo4j
            await create_engagement_node(
                engagement_id=engagement_id,
                post_id=post_id,
                action_type=action_type,
                content=comment,
                strategy_id=strategy_id,
            )

            engagements.append({
                "engagement_id": engagement_id,
                "post_id": post_id,
                "platform": post.get("platform", "unknown"),
                "post_url": post.get("url", ""),
                "action_type": action_type,
                "content": comment,
                "strategy_id": strategy_id,
                "experimental": action.get("experimental", False),
                "validation": validation,
            })

        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        trace = AgentTrace(
            campaign_id=campaign_id,
            agent_type=AgentType.STRATEGY,
            action=ActionType.GENERATE_COMMENT,
            input_data={
                "posts_count": len(enriched_posts),
                "strategy_id": strategy_id,
            },
            output_data={
                "planned_engagements": len(engagements),
                "strategy_reasoning": strategy_plan.get("reasoning", ""),
            },
            duration_ms=duration_ms,
        )

        return {
            "strategy_id": strategy_id,
            "engagements": engagements,
            "reasoning": strategy_plan.get("reasoning", ""),
            "trace": trace.model_dump(),
        }

    @staticmethod
    def _format_history(
        history: list[dict[str, Any]],
        top_strategies: list[dict[str, Any]],
    ) -> str:
        if not history:
            return "No historical data yet. This is a new campaign — experiment freely."

        lines = ["=== Past Engagement Performance ==="]
        for h in history[:20]:
            lines.append(
                f"- {h.get('action_type', '?')} | style: {h.get('style', '?')} | "
                f"impressions: {h.get('impressions', 0)} | "
                f"likes: {h.get('likes', 0)} | replies: {h.get('replies', 0)}"
            )

        if top_strategies:
            lines.append("\n=== Top Performing Strategies ===")
            for s in top_strategies:
                lines.append(
                    f"- {s.get('style', '?')} (tone: {s.get('tone', '?')}) | "
                    f"avg impressions: {s.get('avg_impressions', 0):.0f} | "
                    f"used {s.get('usage_count', 0)} times | "
                    f"confidence: {s.get('confidence', 0):.2f}"
                )

        return "\n".join(lines)

    @staticmethod
    def _format_posts(posts: list[dict[str, Any]]) -> str:
        lines = []
        for i, p in enumerate(posts[:15]):  # Cap to avoid token overflow
            visual = ""
            if p.get("visual_match"):
                visual = f" | VISUAL: {p.get('visual_context', '')[:100]}"
            lines.append(
                f"{i+1}. [{p.get('platform', '?')}] id={p.get('id', '?')} | "
                f"relevance={p.get('relevance_score', 0):.2f} | "
                f"text: {p.get('text', '')[:200]}{visual}"
            )
        return "\n".join(lines) if lines else "No posts available."
