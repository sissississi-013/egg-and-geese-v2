"""Vision Agent — powered by Reka Vision API.

The Visual Scout: a pre-engagement intelligence layer that analyzes
images and videos in scouted social media posts to confirm visual
context matches the product's target problem before an agent engages.

Innovation: the agent doesn't just read text — it *sees* the post,
confirming that a photo actually shows oily hair, not a shampoo ad,
and enriches the engagement context with visual details.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.models.agent_trace import AgentTrace, AgentType, ActionType
from app.models.metrics import ScoutedPost
from app.services.reka_service import RekaVisionService
from app.services.neo4j_service import Neo4jService

logger = logging.getLogger(__name__)


class VisionAgent:
    """Analyzes visual content in scouted posts for context confirmation."""

    @classmethod
    async def analyze_posts(
        cls,
        campaign_id: str,
        posts: list[ScoutedPost],
        expected_context: str,
    ) -> dict[str, Any]:
        """Run visual analysis on all scouted posts that have media.

        For each post with images/video:
        1. Send to Reka Vision for analysis
        2. Check if visual content matches expected context
        3. Enrich post with visual details for the strategy engine
        4. Update Neo4j with visual context

        Args:
            campaign_id: The active campaign ID.
            posts: List of scouted posts to analyze.
            expected_context: What we expect to see (e.g. "oily greasy hair").

        Returns:
            Dict with enriched posts and analysis stats.
        """
        start = datetime.utcnow()
        enriched: list[dict[str, Any]] = []
        skipped = 0
        matched = 0
        not_matched = 0

        for post in posts:
            if not post.media_urls:
                # No media — pass through with text-only context
                enriched.append({
                    **post.model_dump(),
                    "visual_analysis": None,
                    "visual_match": None,
                })
                skipped += 1
                continue

            try:
                logger.info(
                    "VisionAgent: analyzing media for post %s on %s",
                    post.id,
                    post.platform,
                )
                result = await RekaVisionService.confirm_visual_context(
                    media_urls=post.media_urls,
                    expected_context=expected_context,
                )

                post.visual_context = result.get("visual_summary", "")

                if result.get("matches", False):
                    matched += 1
                else:
                    not_matched += 1

                enriched.append({
                    **post.model_dump(),
                    "visual_analysis": result,
                    "visual_match": result.get("matches", False),
                })

                # Update Neo4j node with visual context
                await Neo4jService.run_write(
                    """
                    MATCH (sp:ScoutedPost {id: $id})
                    SET sp.visual_context = $ctx,
                        sp.visual_match = $match,
                        sp.visual_confidence = $conf
                    """,
                    {
                        "id": post.id,
                        "ctx": result.get("visual_summary", ""),
                        "match": result.get("matches", False),
                        "conf": result.get("confidence", 0.0),
                    },
                )

            except Exception as e:
                logger.error("VisionAgent: failed for post %s: %s", post.id, e)
                enriched.append({
                    **post.model_dump(),
                    "visual_analysis": {"error": str(e)},
                    "visual_match": None,
                })

        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        trace = AgentTrace(
            campaign_id=campaign_id,
            agent_type=AgentType.VISION,
            action=ActionType.ANALYZE_VISUAL,
            input_data={
                "total_posts": len(posts),
                "posts_with_media": len(posts) - skipped,
                "expected_context": expected_context,
            },
            output_data={
                "matched": matched,
                "not_matched": not_matched,
                "skipped_no_media": skipped,
            },
            duration_ms=duration_ms,
        )

        return {
            "enriched_posts": enriched,
            "stats": {
                "total": len(posts),
                "with_media": len(posts) - skipped,
                "visual_match": matched,
                "visual_mismatch": not_matched,
                "skipped": skipped,
            },
            "trace": trace.model_dump(),
        }

    @classmethod
    async def deep_analyze_single(
        cls,
        post: ScoutedPost,
        product_context: str,
    ) -> dict[str, Any]:
        """Detailed visual analysis for a high-priority post.

        Uses more specific questions tailored to the product.
        """
        if not post.media_urls:
            return {"analysis": "No media available", "details": {}}

        url = post.media_urls[0]
        is_video = any(
            url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm")
        )

        if is_video:
            result = await RekaVisionService.analyze_video(
                url,
                question=(
                    f"Analyze this video in detail. Context: {product_context}. "
                    "1. What specific problem is shown or discussed? "
                    "2. What products are visible or mentioned? "
                    "3. What is the person's emotional state? "
                    "4. What visual details could be referenced in a helpful comment?"
                ),
            )
        else:
            result = await RekaVisionService.analyze_image(
                url,
                questions=[
                    f"What specific problem related to '{product_context}' is visible?",
                    "What products or brands are shown?",
                    "Describe the person's apparent emotional state.",
                    "What visual details could someone reference to show they understand the problem?",
                    "Is this a genuine user post or an advertisement?",
                ],
            )

        return {
            "analysis": result.get("raw_answer", ""),
            "media_url": url,
            "is_video": is_video,
        }
