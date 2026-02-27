"""Agent trace models – every action an agent takes is recorded."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    INTENT = "intent"
    SCOUT = "scout"
    VISION = "vision"
    STRATEGY = "strategy"
    EXECUTOR = "executor"
    METRICS = "metrics"
    LEARNING = "learning"


class ActionType(str, Enum):
    EXTRACT = "extract"
    SCOUT = "scout"
    ANALYZE_VISUAL = "analyze_visual"
    GENERATE_COMMENT = "generate_comment"
    POST_COMMENT = "post_comment"
    POST_REPLY = "post_reply"
    REPOST = "repost"
    COLLECT_METRICS = "collect_metrics"
    UPDATE_STRATEGY = "update_strategy"


class Platform(str, Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
    INSTAGRAM = "instagram"


class AgentTrace(BaseModel):
    """A single trace event from any agent in the swarm."""

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    campaign_id: str
    agent_type: AgentType
    action: ActionType
    platform: Optional[Platform] = None
    input_data: dict = Field(default_factory=dict)
    output_data: dict = Field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None

    model_config = {"from_attributes": True}
