"""Engagement metrics models for tracking post performance."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EngagementMetrics(BaseModel):
    """Snapshot of engagement metrics for a single post/comment."""

    post_id: str
    platform: str
    impressions: int = 0
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    clicks: int = 0
    follower_delta: int = 0
    sentiment_score: Optional[float] = None  # -1.0 to 1.0
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class StrategyPerformance(BaseModel):
    """Aggregated performance of a particular strategy across all posts."""

    strategy_id: str
    total_engagements: int = 0
    avg_impressions: float = 0.0
    avg_likes: float = 0.0
    avg_replies: float = 0.0
    conversion_rate: float = 0.0
    confidence_score: float = 0.5  # 0-1, starts neutral
    sample_size: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ScoutedPost(BaseModel):
    """A post discovered by the scout agent."""

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    campaign_id: str
    platform: str
    url: str
    author: str = ""
    text: str = ""
    media_urls: list[str] = Field(default_factory=list)
    visual_context: Optional[str] = None  # Reka Vision analysis result
    relevance_score: float = 0.0
    engagement_potential: float = 0.0
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    engaged: bool = False


class EngagementAction(BaseModel):
    """An engagement action taken by the executor agent."""

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    campaign_id: str
    post_id: str
    platform: str
    action_type: str  # comment, reply, repost
    content: str
    strategy_id: str
    posted_at: datetime = Field(default_factory=datetime.utcnow)
    platform_post_id: Optional[str] = None  # ID returned by the platform
