"""Campaign & Product data models (Pydantic + SQLAlchemy)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DateTime, JSON, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


# ---------------------------------------------------------------------------
# SQLAlchemy base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CampaignRow(Base):
    """PostgreSQL campaigns table."""

    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    product_name = Column(String(255), nullable=False)
    product_description = Column(Text, nullable=False)
    target_audience = Column(Text, default="")
    pain_points = Column(JSON, default=list)
    benefits = Column(JSON, default=list)
    platforms = Column(JSON, default=list)  # ["twitter","reddit","instagram"]
    status = Column(
        SAEnum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False
    )
    extracted_entities = Column(JSON, default=dict)
    product_knowledge = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class CampaignCreate(BaseModel):
    name: str
    product_name: str
    product_description: str
    target_audience: str = ""
    platforms: list[str] = Field(default_factory=lambda: ["twitter", "reddit", "instagram"])
    # Pre-extracted data from /from-link or /chat — avoids re-extraction
    extracted_entities: Optional[dict] = None
    campaign_schema: Optional[dict] = None
    gliner_raw: Optional[list] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[CampaignStatus] = None
    target_audience: Optional[str] = None
    platforms: Optional[list[str]] = None


class CampaignOut(BaseModel):
    id: str
    name: str
    product_name: str
    product_description: str
    target_audience: str
    pain_points: list[str]
    benefits: list[str]
    platforms: list[str]
    status: CampaignStatus
    extracted_entities: dict
    product_knowledge: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
