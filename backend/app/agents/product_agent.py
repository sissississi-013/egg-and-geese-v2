"""Product Agent — powered by Senso API + GLiNER claim extraction.

Ensures every agent-generated comment contains only accurate,
verified product information. Acts as a fact-checker between
the strategy engine and execution.

KEY UPGRADE: Uses GLiNER to extract verifiable claims from generated
comments instead of regex. GLiNER can identify product claims,
benefit claims, medical claims, and comparison claims as structured
entities — much more accurate than sentence splitting.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.senso_service import SensoService
from app.services.gliner_service import GLiNERService

logger = logging.getLogger(__name__)


class ProductAgent:
    """Product knowledge gateway — queries and validates product claims.

    Uses GLiNER for structured claim extraction from generated comments,
    then Senso for factual verification against the product knowledge base.
    """

    @classmethod
    async def get_product_context(
        cls,
        product_id: str,
        post_text: str,
    ) -> str:
        """Query Senso for product info relevant to a specific post.

        Constructs a natural-language product brief that the strategy
        engine can use when generating comments.
        """
        query = (
            f"Based on this social media discussion: '{post_text[:300]}' — "
            "what are the most relevant product features, benefits, and "
            "usage tips to mention in a helpful response?"
        )

        result = await SensoService.query_product(query, product_id)

        return result.get("answer", "No product information available.")

    @classmethod
    async def validate_comment(
        cls,
        product_id: str,
        comment: str,
        campaign_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate that a generated comment doesn't contain false claims.

        Uses GLiNER to extract verifiable claims as structured entities,
        then Senso to check each claim against the product knowledge base.

        GLiNER catches claims that regex would miss:
        - "it's clinically proven to reduce oiliness" -> medical claim
        - "way better than Head & Shoulders" -> comparison claim
        - "only $12 for a full bottle" -> price claim

        Returns:
            Dict with ``valid: bool``, ``issues: list[str]``, and
            ``claims_analyzed: list[dict]``.
        """
        # Extract claims using GLiNER (structured, not regex)
        claims = await GLiNERService.extract_claims_from_comment(
            comment, campaign_schema
        )

        issues: list[str] = []
        analyzed_claims: list[dict[str, Any]] = []

        for claim in claims:
            claim_text = claim["text"]
            claim_type = claim["claim_type"]

            try:
                result = await SensoService.validate_claim(claim_text, product_id)
                supported = result.get("supported", True)

                analyzed_claims.append({
                    "text": claim_text,
                    "type": claim_type,
                    "confidence": claim["confidence"],
                    "supported": supported,
                    "corrected": result.get("corrected_claim"),
                })

                if not supported:
                    corrected = result.get("corrected_claim")
                    issues.append(
                        f"[{claim_type}] Unsupported: '{claim_text}'"
                        + (f" -> Suggested: '{corrected}'" if corrected else "")
                    )

                # Flag medical claims for extra scrutiny
                if claim_type == "medical_claim":
                    issues.append(
                        f"[WARNING] Medical claim detected: '{claim_text}' "
                        "— verify compliance with platform policies"
                    )

            except Exception as e:
                logger.warning("Claim validation failed for '%s': %s", claim_text, e)

        return {
            "valid": len([i for i in issues if not i.startswith("[WARNING]")]) == 0,
            "issues": issues,
            "claims_checked": len(claims),
            "claims_analyzed": analyzed_claims,
        }
