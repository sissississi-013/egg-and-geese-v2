"""Metrics collection and storage service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.metrics import EngagementMetrics
from app.services.neo4j_service import Neo4jService
from app.services.openclaw_bridge import OpenClawBridge


class MetricsService:
    """Collects engagement metrics from platforms and stores them in Neo4j."""

    @classmethod
    async def collect_and_store(
        cls,
        campaign_id: str,
        platform: str,
        post_ids: list[str],
    ) -> list[EngagementMetrics]:
        """Collect metrics for a batch of posts and store snapshots in Neo4j.

        Returns:
            List of collected EngagementMetrics.
        """
        raw_metrics = await OpenClawBridge.collect_metrics(platform, post_ids)

        results: list[EngagementMetrics] = []
        for raw in raw_metrics:
            metrics = EngagementMetrics(
                post_id=raw.get("post_id", ""),
                platform=platform,
                impressions=raw.get("impressions", 0),
                likes=raw.get("likes", 0),
                replies=raw.get("replies", 0),
                reposts=raw.get("reposts", 0),
                clicks=raw.get("clicks", 0),
                follower_delta=raw.get("follower_delta", 0),
                sentiment_score=raw.get("sentiment_score"),
            )
            results.append(metrics)

            # Store snapshot in Neo4j
            await Neo4jService.run_write(
                """
                MATCH (e:Engagement {id: $post_id})
                CREATE (m:MetricsSnapshot {
                    impressions: $impressions,
                    likes: $likes,
                    replies: $replies,
                    reposts: $reposts,
                    clicks: $clicks,
                    follower_delta: $follower_delta,
                    sentiment_score: $sentiment_score,
                    collected_at: datetime($collected_at)
                })
                MERGE (e)-[:HAS_METRICS]->(m)
                """,
                {
                    "post_id": metrics.post_id,
                    "impressions": metrics.impressions,
                    "likes": metrics.likes,
                    "replies": metrics.replies,
                    "reposts": metrics.reposts,
                    "clicks": metrics.clicks,
                    "follower_delta": metrics.follower_delta,
                    "sentiment_score": metrics.sentiment_score or 0.0,
                    "collected_at": metrics.collected_at.isoformat(),
                },
            )

        return results

    @classmethod
    async def get_strategy_performance(
        cls,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        """Query Neo4j for aggregated strategy performance."""
        return await Neo4jService.run_query(
            """
            MATCH (c:Campaign {id: $campaign_id})-[:TARGETS]->(:Product)
                  <-[:DISCUSSES]-(:ScoutedPost)<-[:ON_POST]-(e:Engagement)
                  -[:USED_STRATEGY]->(s:Strategy)
            OPTIONAL MATCH (e)-[:HAS_METRICS]->(m:MetricsSnapshot)
            WITH s, e,
                 avg(m.impressions) AS avg_imp,
                 avg(m.likes) AS avg_likes,
                 avg(m.replies) AS avg_replies,
                 count(m) AS sample_size
            RETURN s.id AS strategy_id,
                   s.style AS style,
                   s.tone AS tone,
                   s.confidence_score AS confidence,
                   avg_imp, avg_likes, avg_replies, sample_size
            ORDER BY avg_imp DESC
            """,
            {"campaign_id": campaign_id},
        )

    @classmethod
    async def get_campaign_metrics_summary(
        cls,
        campaign_id: str,
    ) -> dict[str, Any]:
        """Get a high-level metrics summary for a campaign."""
        rows = await Neo4jService.run_query(
            """
            MATCH (c:Campaign {id: $campaign_id})-[:TARGETS]->(:Product)
                  <-[:DISCUSSES]-(:ScoutedPost)<-[:ON_POST]-(e:Engagement)
            OPTIONAL MATCH (e)-[:HAS_METRICS]->(m:MetricsSnapshot)
            RETURN count(DISTINCT e) AS total_engagements,
                   sum(m.impressions) AS total_impressions,
                   sum(m.likes) AS total_likes,
                   sum(m.replies) AS total_replies,
                   sum(m.reposts) AS total_reposts,
                   avg(m.sentiment_score) AS avg_sentiment
            """,
            {"campaign_id": campaign_id},
        )
        if rows:
            return rows[0]
        return {
            "total_engagements": 0,
            "total_impressions": 0,
            "total_likes": 0,
            "total_replies": 0,
            "total_reposts": 0,
            "avg_sentiment": 0.0,
        }
