"""Intent Agent — powered by Fastino GLiNER.

Takes raw business input describing a product and extracts structured
entities: product name, category, target audience, pain points,
benefits, ingredients, competitors. Stores the result in both
PostgreSQL (campaign record) and Neo4j (knowledge graph).
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Any

from app.models.agent_trace import AgentTrace, AgentType, ActionType
from app.models.campaign import CampaignCreate, CampaignStatus
from app.services.gliner_service import GLiNERService
from app.services.senso_service import SensoService
from app.graph.schemas import (
    create_campaign_node,
    create_product_node,
    link_campaign_to_product,
    link_campaign_to_platform,
)

logger = logging.getLogger(__name__)


class IntentAgent:
    """Extracts and anchors business intent from free-text product descriptions."""

    @classmethod
    async def process(
        cls,
        campaign_data: CampaignCreate,
    ) -> dict[str, Any]:
        """Run the full intent extraction pipeline.

        1. GLiNER entity extraction on the product description
        2. Senso product ingestion for accuracy validation later
        3. Store structured data in Neo4j knowledge graph

        Returns:
            Dict with campaign_id, extracted entities, and product_knowledge.
        """
        start = datetime.utcnow()
        campaign_id = uuid.uuid4().hex
        product_id = uuid.uuid4().hex

        # ---- Step 1: GLiNER entity extraction ----
        logger.info("IntentAgent: extracting entities for '%s'", campaign_data.product_name)
        profile = await GLiNERService.extract_product_profile(
            campaign_data.product_description
        )

        extracted = {
            "product_name": profile.get("product_name") or campaign_data.product_name,
            "category": profile.get("category", ""),
            "target_audience": profile.get("target_audience", []),
            "pain_points": profile.get("pain_points", []),
            "benefits": profile.get("benefits", []),
            "ingredients": profile.get("ingredients", []),
            "positioning_tone": profile.get("positioning_tone", {}),
            "raw_entities": profile.get("entities", []),
        }

        # ---- Step 2: Senso product ingestion ----
        logger.info("IntentAgent: ingesting product into Senso KB")
        senso_result = await SensoService.ingest_product(
            product_name=campaign_data.product_name,
            description=campaign_data.product_description,
            metadata={
                "category": extracted["category"],
                "benefits": extracted["benefits"],
                "ingredients": extracted["ingredients"],
            },
        )

        product_knowledge = {
            "senso_product_id": senso_result.get("id", ""),
            "knowledge_summary": senso_result.get("summary", ""),
            **extracted,
        }

        # ---- Step 3: Neo4j graph creation ----
        logger.info("IntentAgent: creating knowledge graph nodes")
        await create_campaign_node(
            campaign_id=campaign_id,
            name=campaign_data.name,
            product_name=extracted["product_name"],
            target_audience=campaign_data.target_audience
            or ", ".join(extracted["target_audience"]),
        )

        await create_product_node(
            product_id=product_id,
            name=extracted["product_name"],
            category=extracted["category"],
            benefits=extracted["benefits"],
            pain_points_solved=extracted["pain_points"],
            ingredients=extracted["ingredients"],
        )

        await link_campaign_to_product(campaign_id, product_id)

        for platform in campaign_data.platforms:
            await link_campaign_to_platform(campaign_id, platform)

        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        # Build trace
        trace = AgentTrace(
            campaign_id=campaign_id,
            agent_type=AgentType.INTENT,
            action=ActionType.EXTRACT,
            input_data={
                "name": campaign_data.name,
                "product_name": campaign_data.product_name,
                "description": campaign_data.product_description[:500],
            },
            output_data=extracted,
            duration_ms=duration_ms,
        )

        return {
            "campaign_id": campaign_id,
            "product_id": product_id,
            "extracted_entities": extracted,
            "product_knowledge": product_knowledge,
            "trace": trace.model_dump(),
        }
