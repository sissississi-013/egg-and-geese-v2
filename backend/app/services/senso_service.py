"""Senso API client for product knowledge accuracy validation.

Senso (https://docs.senso.ai) provides a Context OS SDK for ingesting,
querying, and validating domain knowledge. We use it to ensure that
agent-generated comments contain accurate product information — no
hallucinated ingredients, fake stats, or unsupported claims.

Auth: X-API-Key header.  Keys start with 'tgr_'.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SensoService:
    """Wraps the Senso API to ingest product data and validate claims.

    Ensures that agent-generated comments contain accurate product
    information — no hallucinated ingredients, fake stats, or
    unsupported claims.
    """

    BASE_URL = settings.senso_base_url

    @classmethod
    def _headers(cls) -> dict[str, str]:
        return {
            "X-API-Key": settings.senso_api_key,
            "Content-Type": "application/json",
        }

    @classmethod
    async def ingest_product(
        cls,
        product_name: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ingest product info into Senso's knowledge base.

        Args:
            product_name: Name of the product.
            description: Full product description, ingredients, usage notes.
            metadata: Additional structured data (price, SKU, etc.).

        Returns:
            Product profile including generated knowledge ID.
        """
        payload = {
            "name": product_name,
            "description": description,
            "metadata": metadata or {},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/knowledge/ingest",
                json=payload,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def query_product(
        cls,
        query: str,
        product_id: str | None = None,
    ) -> dict[str, Any]:
        """Query the Senso knowledge base for product-specific info.

        Args:
            query: Natural language question about the product.
            product_id: Optional ID to scope to a specific product.

        Returns:
            Answer with source citations from the ingested data.
        """
        payload: dict[str, Any] = {"query": query}
        if product_id:
            payload["product_id"] = product_id

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/knowledge/query",
                json=payload,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def validate_claim(
        cls,
        claim: str,
        product_id: str,
    ) -> dict[str, Any]:
        """Check whether a claim about the product is factually supported.

        Returns:
            Dict with ``supported: bool``, ``confidence: float``,
            and ``corrected_claim: str | None``.
        """
        payload = {
            "claim": claim,
            "product_id": product_id,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/knowledge/validate",
                json=payload,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()
