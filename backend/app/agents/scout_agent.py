"""Scout Agent — powered by Yutori + GLiNER entity-driven scoring.

Launches multi-platform scouting runs to discover social media posts
that discuss pain points relevant to a campaign's product.

KEY DIFFERENTIATOR: Every scouted post gets GLiNER entity extraction
using the campaign's dynamic entity schema. Posts are scored based on
ENTITY OVERLAP — not just keyword matching. This means the system
understands that "my scalp is always greasy" matches a campaign
targeting "oily hair" even though the exact words differ, because
GLiNER extracts the underlying "pain point" entity from both.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.models.agent_trace import AgentTrace, AgentType, ActionType, Platform
from app.models.metrics import ScoutedPost
from app.services.yutori_service import YutoriService
from app.services.gliner_service import GLiNERService
from app.graph.schemas import create_scouted_post_node
from app.services.neo4j_service import Neo4jService

logger = logging.getLogger(__name__)


class ScoutAgent:
    """Discovers relevant social media discussions using entity-driven scoring."""

    @classmethod
    async def scout(
        cls,
        campaign_id: str,
        product_id: str,
        pain_points: list[str],
        platforms: list[str],
        campaign_schema: dict[str, Any] | None = None,
        max_results_per_platform: int = 30,
    ) -> dict[str, Any]:
        """Run a full scouting cycle with GLiNER entity-level scoring.

        1. Build search queries from pain points
        2. Launch Yutori scout runs per platform
        3. Run GLiNER entity extraction on EVERY discovered post
        4. Score posts using entity overlap (not just classification)
        5. Detect engagement signals (asking for recs, sharing experiences)
        6. Store qualified posts + their entity profiles in Neo4j

        Returns:
            Dict with discovered posts, entity analysis, and stats.
        """
        start = datetime.utcnow()
        all_posts: list[ScoutedPost] = []

        # Build the campaign entity schema if not provided
        if not campaign_schema:
            campaign_schema = GLiNERService.build_campaign_schema({
                "pain_points": pain_points,
                "benefits": [],
                "ingredients": [],
                "category": "",
            })

        # Build diverse search queries from pain points
        queries = cls._build_search_queries(pain_points)
        logger.info(
            "ScoutAgent: scouting %d platforms with %d queries (entity-driven)",
            len(platforms),
            len(queries),
        )

        for query in queries:
            # Launch scout across all requested platforms
            scout_result = await YutoriService.create_scout(
                query=query,
                platforms=platforms,
                max_results=max_results_per_platform,
                recency_hours=48,
            )

            run_id = scout_result.get("run_id", "")

            # Poll for completion (with timeout)
            for _ in range(30):  # max 5 min wait
                status = await YutoriService.get_scout_status(run_id)
                if status in ("completed", "done"):
                    break
                await asyncio.sleep(10)

            raw_results = await YutoriService.get_scout_results(run_id)
            posts = YutoriService.results_to_scouted_posts(
                raw_results, campaign_id
            )
            all_posts.extend(posts)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_posts: list[ScoutedPost] = []
        for post in all_posts:
            if post.url not in seen_urls:
                seen_urls.add(post.url)
                unique_posts.append(post)

        # ── GLiNER Entity-Driven Scoring ─────────────────────────────
        # This is where GLiNER shines: extract entities from each post
        # using the campaign's schema, then score based on entity overlap.
        # Much more accurate than keyword matching or LLM classification.
        scored_posts = await cls._score_posts_with_entities(
            unique_posts, campaign_schema
        )

        # Filter: only keep posts above relevance threshold
        qualified = [p for p in scored_posts if p.relevance_score >= 0.3]

        # Sort by relevance (highest first)
        qualified.sort(key=lambda p: p.relevance_score, reverse=True)

        # Store in Neo4j with entity metadata
        for post in qualified:
            await create_scouted_post_node(
                post_id=post.id,
                platform=post.platform,
                url=post.url,
                text=post.text[:1000],
                visual_context=post.visual_context,
                relevance_score=post.relevance_score,
                product_id=product_id,
            )

        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        # Count engagement signals across qualified posts
        signal_counts = cls._count_signals(qualified)

        trace = AgentTrace(
            campaign_id=campaign_id,
            agent_type=AgentType.SCOUT,
            action=ActionType.SCOUT,
            input_data={
                "pain_points": pain_points,
                "platforms": platforms,
                "queries": queries,
                "schema_labels": campaign_schema.get("scouting_labels", []),
            },
            output_data={
                "total_discovered": len(all_posts),
                "unique": len(unique_posts),
                "qualified": len(qualified),
                "engagement_signals": signal_counts,
            },
            duration_ms=duration_ms,
        )

        return {
            "posts": [p.model_dump() for p in qualified],
            "stats": {
                "total_discovered": len(all_posts),
                "unique": len(unique_posts),
                "qualified": len(qualified),
                "by_platform": cls._count_by_platform(qualified),
                "engagement_signals": signal_counts,
            },
            "trace": trace.model_dump(),
        }

    @staticmethod
    def _build_search_queries(pain_points: list[str]) -> list[str]:
        """Expand pain points into diverse search queries."""
        queries: list[str] = []
        for pp in pain_points:
            queries.append(pp)
            queries.append(f"{pp} problem")
            queries.append(f"struggling with {pp}")
            queries.append(f"anyone else deal with {pp}")
            queries.append(f"help with {pp}")
        # Deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for q in queries:
            lower = q.lower()
            if lower not in seen:
                seen.add(lower)
                result.append(q)
        return result[:10]  # Cap at 10 queries to manage API costs

    @classmethod
    async def _score_posts_with_entities(
        cls,
        posts: list[ScoutedPost],
        campaign_schema: dict[str, Any],
    ) -> list[ScoutedPost]:
        """Use GLiNER to extract entities from each post and score
        based on entity overlap with the campaign's product entities.

        This replaces the old classify_text approach. Instead of asking
        "is this post about oily hair?" (classification), we ask
        "what entities exist in this post?" (extraction) and then
        compute overlap with campaign entities.

        This is more accurate because:
        1. We see exactly WHICH entities matched (debuggable)
        2. We can weight different entity types differently
        3. We capture engagement signals (asking for recs, etc.)
        """
        # Prepare batch input
        post_dicts = [
            {"id": post.id, "text": post.text}
            for post in posts
        ]

        # Run GLiNER batch analysis (parallel, fast)
        analyses = await GLiNERService.batch_analyze_posts(
            post_dicts, campaign_schema
        )

        # Map analysis results back to posts
        analysis_map = {a["post_id"]: a for a in analyses}

        for post in posts:
            analysis = analysis_map.get(post.id)
            if not analysis:
                continue

            # Compute composite relevance score
            overlap = analysis.get("overlap_score", 0.0)
            signals = analysis.get("signals", {})

            # Boost score for high-engagement-potential signals
            score = overlap
            if signals.get("is_asking_recommendation"):
                score = min(1.0, score + 0.3)  # Huge boost — they want product recs!
            if signals.get("is_sharing_experience"):
                score = min(1.0, score + 0.15)  # They're engaged with the topic
            if signals.get("is_complaining"):
                score = min(1.0, score + 0.2)  # Frustrated user = opportunity

            post.relevance_score = round(score, 3)

        return posts

    @staticmethod
    def _count_signals(posts: list[ScoutedPost]) -> dict[str, int]:
        """Count engagement signals across qualified posts.
        (Stored in trace for the LearningAgent to analyze.)
        """
        # This would require storing signals on posts; for now return empty
        return {
            "total_qualified": len(posts),
        }

    @staticmethod
    def _count_by_platform(posts: list[ScoutedPost]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in posts:
            counts[p.platform] = counts.get(p.platform, 0) + 1
        return counts
