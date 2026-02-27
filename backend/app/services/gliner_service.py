"""GLiNER 2 service — zero-shot information extraction.

GLiNER 2 (github.com/fastino-ai/GLiNER2) is Fastino's unified schema-based
information extraction model that handles three tasks in one forward pass:
  - Named Entity Recognition (NER)
  - Text Classification
  - Structured Data Extraction (JSON)

The model is 205M–340M parameters, CPU-optimized (100–250ms latency).

=== WHY GLiNER IS THE BACKBONE OF EGG & GEESE ===

Unlike LLMs that generate text (and can hallucinate), GLiNER extracts
GROUNDED SPANS — actual text that exists in the input. This makes it:
  1. More accurate for entity extraction than prompting an LLM
  2. Deterministic — same input always yields same entities
  3. Fast — 100-250ms vs 2-5s for an LLM call
  4. Schema-flexible — define ANY entity types per campaign

GLiNER powers EVERY stage of the pipeline:
  - Intent Anchoring: extract product entities from pages (primary engine)
  - Scouting: extract entities from social posts to score relevance
  - Engagement: validate generated comments contain correct entities
  - Learning: extract entities from successful/failed posts for analysis
  - Cross-post matching: same entities regardless of phrasing

Supports three modes:
  - "local"   → loads the GLiNER model directly into memory
  - "pioneer" → calls a Pioneer-deployed fine-tuned inference endpoint
  - "fastino" → calls Fastino's hosted POST /gliner-2 endpoint
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local model singleton (lazy-loaded on first call)
# ---------------------------------------------------------------------------
_model = None


def _get_local_model():
    """Load the GLiNER model into memory (once)."""
    global _model
    if _model is None:
        from gliner import GLiNER  # type: ignore[import-untyped]

        model_id = settings.gliner_model_id
        logger.info("Loading GLiNER model: %s (this may take a moment)...", model_id)
        _model = GLiNER.from_pretrained(model_id)
        logger.info("GLiNER model loaded successfully")
    return _model


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class GLiNERService:
    """Zero-shot information extraction powered by GLiNER 2.

    GLiNER is the primary structured extraction engine across the entire
    Egg & Geese pipeline. Every piece of text — product pages, social posts,
    generated comments, engagement results — gets GLiNER entity extraction.

    The key differentiator: GLiNER extracts GROUNDED SPANS from source text.
    It cannot hallucinate entities because it only returns text that actually
    exists in the input.
    """

    # ── Core NER ──────────────────────────────────────────────────

    @classmethod
    async def extract_entities(
        cls,
        text: str,
        labels: list[str] | None = None,
        threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run Named Entity Recognition on *text*.

        Args:
            text: The raw text to extract entities from.
            labels: Entity labels to detect. GLiNER accepts ANY labels —
                    e.g. ["product_name", "pain_point", "ingredient"].
                    This zero-shot capability means we can create
                    campaign-specific schemas on the fly.
            threshold: Minimum confidence score (0-1). Defaults to config.

        Returns:
            List of ``{"text": ..., "label": ..., "score": ...,
                        "start": ..., "end": ...}`` dicts.
        """
        if labels is None:
            labels = [
                "product name",
                "product category",
                "target audience",
                "pain point",
                "benefit",
                "ingredient",
                "brand",
                "price",
                "competitor",
            ]

        threshold = threshold or settings.gliner_threshold

        mode = settings.gliner_mode
        if mode == "fastino":
            return await cls._predict_via_fastino(
                text, labels, threshold, task="extract_entities"
            )
        elif mode == "pioneer" and settings.pioneer_endpoint_url:
            return await cls._predict_via_pioneer(text, labels, threshold)
        else:
            return await cls._predict_local(text, labels, threshold)

    @classmethod
    async def _predict_local(
        cls,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> list[dict[str, Any]]:
        """Run prediction using the locally-loaded GLiNER model."""
        model = await asyncio.to_thread(_get_local_model)

        entities = await asyncio.to_thread(
            model.predict_entities,
            text,
            labels,
            threshold=threshold,
        )

        return [
            {
                "text": ent.get("text", ent.get("span", "")),
                "label": ent.get("label", ""),
                "score": round(ent.get("score", 0.0), 4),
                "start": ent.get("start", 0),
                "end": ent.get("end", 0),
            }
            for ent in entities
        ]

    @classmethod
    async def _predict_via_fastino(
        cls,
        text: str,
        schema: list[str],
        threshold: float,
        task: str = "extract_entities",
    ) -> list[dict[str, Any]]:
        """Call Fastino's hosted POST /gliner-2 endpoint.

        Fastino's API accepts:
            {text, schema, task, threshold}
        where task is one of: extract_entities, classify_text, extract_json

        Auth: Pioneer API key in Authorization header.
        """
        payload = {
            "text": text,
            "schema": schema,
            "task": task,
            "threshold": threshold,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.pioneer_api_key:
            headers["X-API-Key"] = settings.pioneer_api_key

        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.post(
                f"{settings.fastino_base_url}/gliner-2",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            # Pioneer API wraps result in {"result": ..., "token_usage": ...}
            result = data.get("result", data)

            # Normalize response based on task
            if task == "classify_text":
                return result if isinstance(result, list) else [result]
            elif task == "extract_json":
                return result if isinstance(result, list) else [result]
            else:
                # Entity extraction: result = {"entities": {"label": [values]}}
                raw_entities = result.get("entities", result) if isinstance(result, dict) else result
                if isinstance(raw_entities, dict):
                    # Convert {"label": [values]} format to list of entities
                    flat: list[dict[str, Any]] = []
                    for label, values in raw_entities.items():
                        if isinstance(values, list):
                            for val in values:
                                flat.append({
                                    "text": val,
                                    "label": label,
                                    "score": 1.0,
                                    "start": 0,
                                    "end": 0,
                                })
                    return flat
                elif isinstance(raw_entities, list):
                    return [
                        {
                            "text": ent.get("text", ent.get("span", "")),
                            "label": ent.get("label", ""),
                            "score": round(ent.get("score", 0.0), 4),
                            "start": ent.get("start", 0),
                            "end": ent.get("end", 0),
                        }
                        for ent in raw_entities
                    ]
                return []

    @classmethod
    async def _predict_via_pioneer(
        cls,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> list[dict[str, Any]]:
        """Call a Pioneer-deployed fine-tuned GLiNER inference endpoint."""
        payload = {
            "text": text,
            "labels": labels,
            "threshold": threshold,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.pioneer_api_key:
            headers["Authorization"] = f"Bearer {settings.pioneer_api_key}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                settings.pioneer_endpoint_url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            entities = data if isinstance(data, list) else data.get("entities", [])
            return [
                {
                    "text": ent.get("text", ent.get("span", "")),
                    "label": ent.get("label", ""),
                    "score": round(ent.get("score", 0.0), 4),
                    "start": ent.get("start", 0),
                    "end": ent.get("end", 0),
                }
                for ent in entities
            ]

    # ── Zero-shot classification ─────────────────────────────────

    @classmethod
    async def classify_text(
        cls,
        text: str,
        labels: list[str],
    ) -> dict[str, float]:
        """Zero-shot text classification.

        In Fastino hosted mode, uses the native classify_text task.
        In local/pioneer mode, approximates via NER entity scores.

        Returns:
            Dict mapping each label to its confidence score (0-1).
        """
        if settings.gliner_mode == "fastino":
            # Use Fastino's native classify_text task
            try:
                result = await cls._predict_via_fastino(
                    text, labels, threshold=0.1, task="classify_text"
                )
                # Response should be label->score mapping
                if isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], dict):
                        # Might be a dict with label scores
                        scores = {label: 0.0 for label in labels}
                        for item in result:
                            label = item.get("label", "")
                            score = item.get("score", 0.0)
                            if label in scores:
                                scores[label] = max(scores[label], score)
                        return scores
                return {label: 0.0 for label in labels}
            except Exception:
                logger.warning("Fastino classify_text failed, falling back to NER")

        # Fallback: use NER-based classification
        entities = await cls.extract_entities(
            text, labels=labels, threshold=0.1
        )

        scores: dict[str, float] = {label: 0.0 for label in labels}
        for ent in entities:
            label = ent.get("label", "")
            score = ent.get("score", 0.0)
            if label in scores:
                scores[label] = max(scores[label], score)

        return scores

    # ── Structured JSON extraction ───────────────────────────────

    @classmethod
    async def extract_json(
        cls,
        text: str,
        schema: list[str],
    ) -> dict[str, Any]:
        """Extract structured JSON data from text.

        Only available in Fastino hosted mode. Falls back to NER-based
        extraction in other modes.
        """
        if settings.gliner_mode == "fastino":
            try:
                result = await cls._predict_via_fastino(
                    text, schema, threshold=0.3, task="extract_json"
                )
                if isinstance(result, list) and len(result) > 0:
                    return result[0] if isinstance(result[0], dict) else {"data": result}
                return {"data": result}
            except Exception:
                logger.warning("Fastino extract_json failed, falling back to NER")

        # Fallback: use NER and group into a dict
        entities = await cls.extract_entities(text, labels=schema)
        grouped: dict[str, list[str]] = {}
        for ent in entities:
            key = ent.get("label", "unknown").replace(" ", "_")
            val = ent.get("text", "")
            if val:
                grouped.setdefault(key, []).append(val)
        return grouped

    # ── High-level product profile extraction ────────────────────

    @classmethod
    async def extract_product_profile(cls, description: str) -> dict[str, Any]:
        """Extract a full product profile from free-text.

        Uses GLiNER to extract GROUNDED SPANS across all relevant categories,
        then organizes them into a structured profile dict.

        This is the primary entry point called by the IntentAgent.
        GLiNER extractions are grounded in the source text — every entity
        is a real span from the input, not hallucinated.
        """
        entities = await cls.extract_entities(description)

        # Group entities by label
        profile: dict[str, list[str]] = {}
        for ent in entities:
            label = ent.get("label", "unknown")
            text = ent.get("text", "")
            if text:
                key = label.replace(" ", "_")
                profile.setdefault(key, []).append(text)

        # Run classification for tone/positioning
        tone_scores = await cls.classify_text(
            description,
            labels=["premium", "budget", "natural", "clinical", "fun", "serious"],
        )

        return {
            "entities": entities,
            "grouped": profile,
            "product_name": profile.get("product_name", [""])[0],
            "category": profile.get("product_category", [""])[0],
            "target_audience": profile.get("target_audience", []),
            "pain_points": profile.get("pain_point", []),
            "benefits": profile.get("benefit", []),
            "ingredients": profile.get("ingredient", []),
            "positioning_tone": tone_scores,
        }

    # ── Campaign Entity Schema Builder ─────────────────────────

    @classmethod
    def build_campaign_schema(cls, product_profile: dict[str, Any]) -> dict[str, Any]:
        """Build a dynamic, campaign-specific GLiNER entity schema.

        THIS IS THE KEY DIFFERENTIATOR: Instead of using the same static
        labels for every campaign, we build a schema from the extracted
        product entities. This means:
        - A shampoo campaign scouts for hair/scalp-specific entities
        - A SaaS campaign scouts for software/integration entities
        - A food product campaign scouts for taste/dietary entities

        The schema is used by ScoutAgent and StrategyAgent to:
        1. Extract entities from scouted social posts
        2. Score post relevance via entity overlap
        3. Validate generated comments contain correct entities

        Returns:
            Dict with:
            - scouting_labels: labels to extract from social posts
            - validation_labels: labels to check in generated comments
            - pain_point_terms: specific pain point phrases to match
            - benefit_terms: specific benefit phrases to match
            - product_terms: brand/product name terms to detect
        """
        pain_points = product_profile.get("pain_points", [])
        benefits = product_profile.get("benefits", [])
        ingredients = product_profile.get("ingredients", [])
        category = product_profile.get("category", "")

        # Core labels for scouting social media posts
        scouting_labels = [
            "pain point",
            "problem description",
            "product recommendation",
            "question",
            "complaint",
            "personal experience",
            "product mention",
        ]

        # Add category-specific labels dynamically
        category_labels = {
            "skincare": ["skin concern", "skin type", "skincare routine", "dermatologist recommendation"],
            "haircare": ["hair concern", "hair type", "hair routine", "styling problem"],
            "software": ["technical issue", "feature request", "integration", "workflow problem"],
            "food": ["dietary need", "taste preference", "allergy", "meal planning"],
            "fitness": ["fitness goal", "workout problem", "nutrition need", "recovery"],
            "fashion": ["style preference", "fit issue", "occasion", "budget concern"],
        }

        # Match category to add domain-specific labels
        cat_lower = category.lower()
        for domain, labels in category_labels.items():
            if domain in cat_lower:
                scouting_labels.extend(labels)
                break

        # Labels for validating generated comments
        validation_labels = [
            "product claim",
            "benefit claim",
            "ingredient mention",
            "medical claim",
            "price claim",
            "comparison claim",
        ]

        return {
            "scouting_labels": scouting_labels,
            "validation_labels": validation_labels,
            "pain_point_terms": pain_points,
            "benefit_terms": benefits,
            "ingredient_terms": ingredients,
            "product_terms": [
                product_profile.get("product_name", ""),
                product_profile.get("grouped", {}).get("brand", [""])[0],
            ],
            "category": category,
        }

    # ── Social Post Analysis (for ScoutAgent) ──────────────────

    @classmethod
    async def analyze_social_post(
        cls,
        post_text: str,
        campaign_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Run GLiNER entity extraction on a scouted social media post
        using the campaign's dynamic entity schema.

        This is the heart of the entity-driven scouting pipeline:
        1. Extract entities from the post using campaign-specific labels
        2. Compute entity overlap with campaign's known pain points
        3. Detect if the post is asking for recommendations

        Returns:
            Dict with extracted entities, overlap score, and signals.
        """
        labels = campaign_schema.get("scouting_labels", [
            "pain point", "product recommendation", "question",
            "complaint", "personal experience",
        ])

        entities = await cls.extract_entities(post_text, labels=labels, threshold=0.3)

        # Group by label
        grouped: dict[str, list[str]] = {}
        for ent in entities:
            label = ent.get("label", "").replace(" ", "_")
            text = ent.get("text", "")
            if text:
                grouped.setdefault(label, []).append(text)

        # Compute entity overlap with campaign pain points
        overlap_score = cls._compute_entity_overlap(
            post_entities=grouped,
            campaign_pain_points=campaign_schema.get("pain_point_terms", []),
            campaign_benefits=campaign_schema.get("benefit_terms", []),
        )

        # Detect engagement signals
        signals = {
            "is_asking_recommendation": bool(grouped.get("product_recommendation") or grouped.get("question")),
            "is_sharing_experience": bool(grouped.get("personal_experience")),
            "is_complaining": bool(grouped.get("complaint")),
            "has_relevant_pain_point": overlap_score > 0.3,
            "entity_count": sum(len(v) for v in grouped.values()),
        }

        return {
            "entities": entities,
            "grouped": grouped,
            "overlap_score": overlap_score,
            "signals": signals,
        }

    @staticmethod
    def _compute_entity_overlap(
        post_entities: dict[str, list[str]],
        campaign_pain_points: list[str],
        campaign_benefits: list[str],
    ) -> float:
        """Compute semantic overlap between post entities and campaign terms.

        Uses fuzzy string matching on extracted entity spans against
        the campaign's known pain points and benefits.

        Returns:
            Float 0.0-1.0 representing entity-level relevance.
        """
        if not campaign_pain_points and not campaign_benefits:
            return 0.0

        all_post_text = " ".join(
            text.lower()
            for spans in post_entities.values()
            for text in spans
        )

        if not all_post_text:
            return 0.0

        # Check how many campaign terms appear (as substrings) in post entities
        all_campaign_terms = campaign_pain_points + campaign_benefits
        matches = 0
        for term in all_campaign_terms:
            term_lower = term.lower()
            # Check for substring overlap or word-level match
            term_words = set(term_lower.split())
            post_words = set(all_post_text.split())
            common = term_words & post_words
            if len(common) >= max(1, len(term_words) // 2):
                matches += 1

        return min(1.0, matches / max(1, len(all_campaign_terms)))

    # ── Comment Claim Extraction (for ProductAgent) ────────────

    @classmethod
    async def extract_claims_from_comment(
        cls,
        comment: str,
        campaign_schema: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Extract verifiable product claims from a generated comment.

        Replaces the old regex-based claim extraction with GLiNER's
        structured span extraction. This catches claims that regex
        would miss, like comparative statements or implied benefits.

        Returns:
            List of claim dicts with text, label, and confidence.
        """
        labels = [
            "product claim",
            "benefit claim",
            "ingredient mention",
            "medical claim",
            "comparison claim",
            "price claim",
            "testimonial",
        ]

        if campaign_schema:
            labels = campaign_schema.get("validation_labels", labels)

        entities = await cls.extract_entities(comment, labels=labels, threshold=0.3)

        claims: list[dict[str, Any]] = []
        seen_texts: set[str] = set()
        for ent in entities:
            text = ent.get("text", "").strip()
            if text and text.lower() not in seen_texts and len(text) > 5:
                seen_texts.add(text.lower())
                claims.append({
                    "text": text,
                    "claim_type": ent.get("label", "unknown"),
                    "confidence": ent.get("score", 0.0),
                })

        return claims

    # ── Entity-level Engagement Analysis (for LearningAgent) ───

    @classmethod
    async def analyze_engagement_entities(
        cls,
        comment_text: str,
        post_text: str,
        campaign_schema: dict[str, Any],
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extract and analyze entities from an engagement for learning.

        The LearningAgent uses this to understand WHICH SPECIFIC ENTITIES
        in a comment drove engagement (or didn't).

        This is how the system learns at an entity level:
        - "Mentioning 'ceramides' got 3x more likes than 'hydration'"
        - "Posts about 'itchy scalp' had 2x higher reply rates"
        - "Testimonial-style claims outperformed factual claims"

        Returns:
            Dict with comment entities, post entities, and entity-level
            performance mapping.
        """
        # Extract entities from the comment we posted
        comment_labels = campaign_schema.get("validation_labels", [
            "product claim", "benefit claim", "ingredient mention",
        ])
        comment_entities = await cls.extract_entities(
            comment_text, labels=comment_labels, threshold=0.3
        )

        # Extract entities from the post we replied to
        post_labels = campaign_schema.get("scouting_labels", [
            "pain point", "question", "complaint",
        ])
        post_entities = await cls.extract_entities(
            post_text, labels=post_labels, threshold=0.3
        )

        # Map entities to performance if metrics provided
        entity_performance: list[dict[str, Any]] = []
        if metrics:
            for ent in comment_entities:
                entity_performance.append({
                    "entity_text": ent.get("text", ""),
                    "entity_type": ent.get("label", ""),
                    "confidence": ent.get("score", 0.0),
                    "impressions": metrics.get("impressions", 0),
                    "likes": metrics.get("likes", 0),
                    "replies": metrics.get("replies", 0),
                })

        return {
            "comment_entities": comment_entities,
            "post_entities": post_entities,
            "entity_performance": entity_performance,
            "entity_match": cls._compute_entity_overlap(
                {ent.get("label", ""): [ent.get("text", "")] for ent in comment_entities},
                campaign_schema.get("pain_point_terms", []),
                campaign_schema.get("benefit_terms", []),
            ),
        }

    # ── Batch Post Analysis ────────────────────────────────────

    @classmethod
    async def batch_analyze_posts(
        cls,
        posts: list[dict[str, str]],
        campaign_schema: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Analyze multiple social posts in parallel using GLiNER.

        Takes advantage of GLiNER's speed (100-250ms per call) to
        analyze many posts concurrently. This is significantly faster
        than sending each post to an LLM.

        Args:
            posts: List of dicts with at least 'id' and 'text' keys.
            campaign_schema: The campaign's dynamic entity schema.

        Returns:
            List of analysis results, one per post.
        """
        tasks = [
            cls.analyze_social_post(
                post.get("text", ""),
                campaign_schema,
            )
            for post in posts
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyzed: list[dict[str, Any]] = []
        for post, result in zip(posts, results):
            if isinstance(result, Exception):
                logger.warning("GLiNER analysis failed for post %s: %s", post.get("id"), result)
                analyzed.append({
                    "post_id": post.get("id", ""),
                    "entities": [],
                    "grouped": {},
                    "overlap_score": 0.0,
                    "signals": {},
                    "error": str(result),
                })
            else:
                result["post_id"] = post.get("id", "")
                analyzed.append(result)

        return analyzed
