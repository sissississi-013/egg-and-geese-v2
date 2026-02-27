"""Campaign CRUD and lifecycle API endpoints."""

from __future__ import annotations

import uuid
import re
import json
import html as html_mod
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.campaign import (
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    CampaignStatus,
)
from app.orchestrator.swarm import SwarmCoordinator
from app.services.gliner_service import GLiNERService
from app.services.claude_service import ClaudeService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

# In-memory store (replace with PostgreSQL in production)
_campaigns: dict[str, dict] = {}


# ── Smart Campaign Creation (static paths — MUST come before /{campaign_id}) ─


class LinkExtractRequest(BaseModel):
    url: str


@router.post("/from-link")
async def extract_from_link(data: LinkExtractRequest):
    """Scrape a product URL — GLiNER extracts grounded spans FIRST,
    Claude synthesizes and enriches SECOND.

    Architecture principle: GLiNER provides the structured backbone
    (entities that ACTUALLY EXIST in the page text), Claude fills in
    the semantic gaps (descriptions, tone, audience reasoning).
    """
    import logging
    logger = logging.getLogger("extract_from_link")

    # ── Step 1: Scrape the page ──────────────────────────────────────────
    # Many e-commerce sites (Amazon, etc.) aggressively block bots.
    # We use full browser-like headers, cookie handling, and retry logic.
    BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        # Do NOT include 'br' (Brotli) — httpx can't decompress it,
        # resulting in garbled binary text. gzip/deflate are fine.
        "Accept-Encoding": "gzip, deflate",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    html = ""
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            verify=False,
            # Enable cookie persistence within the session
            cookies=httpx.Cookies(),
        ) as client:
            resp = await client.get(data.url, headers=BROWSER_HEADERS)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as e:
        raise HTTPException(400, f"Failed to fetch URL: {str(e)}")

    # Strip scripts, styles, tags -> clean text
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # ── Amazon-specific: try structured extraction from HTML first ────────
    # Amazon blocks scrapers and returns thin error pages. If detected,
    # extract from structured data (ld+json, meta tags) in the raw HTML.
    is_amazon = "amazon.com" in data.url.lower() or "amzn." in data.url.lower()
    structured_text = ""

    def _clean_json_str(s: str) -> str:
        """Strip control characters that break json.loads."""
        return re.sub(r'[\x00-\x1f\x7f]', ' ', s)

    def _extract_ld_json_product(html_src: str) -> str:
        """Extract product info from ld+json blocks, tolerant of messy HTML."""
        parts: list[str] = []
        ld_json_matches = re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html_src, re.DOTALL | re.IGNORECASE,
        )
        for ld_raw in ld_json_matches:
            try:
                cleaned = _clean_json_str(ld_raw.strip())
                ld_data = json.loads(cleaned)
                items = ld_data if isinstance(ld_data, list) else [ld_data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("@type", "")
                    if isinstance(itype, list):
                        itype = " ".join(itype)
                    if any(t in itype for t in (
                        "Product", "IndividualProduct", "ProductGroup",
                        "ItemPage", "WebPage",
                    )):
                        if item.get("name"):
                            parts.append(f"Product: {item['name']}")
                        if item.get("description"):
                            desc = re.sub(r'<[^>]+>', '', str(item['description']))
                            parts.append(f"Description: {html_mod.unescape(desc)}")
                        if item.get("brand"):
                            bv = item["brand"]
                            if isinstance(bv, dict):
                                bv = bv.get("name", "")
                            parts.append(f"Brand: {bv}")
                        offers = item.get("offers", item.get("offer", {}))
                        if isinstance(offers, dict) and offers.get("price"):
                            parts.append(f"Price: ${offers['price']}")
                        elif isinstance(offers, list):
                            for o in offers:
                                if isinstance(o, dict) and o.get("price"):
                                    parts.append(f"Price: ${o['price']}")
                                    break
                        if item.get("aggregateRating"):
                            r = item["aggregateRating"]
                            parts.append(
                                f"Rating: {r.get('ratingValue', '?')}/5 "
                                f"({r.get('reviewCount', '?')} reviews)"
                            )
                        if item.get("ingredients"):
                            parts.append(f"Ingredients: {item['ingredients']}")
                        if item.get("category"):
                            parts.append(f"Category: {item['category']}")
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return " ".join(parts)

    def _extract_meta_tags(html_src: str) -> str:
        """Extract all useful meta tags."""
        parts: list[str] = []
        # <title> tag
        title_tag = re.search(r'<title[^>]*>(.*?)</title>', html_src, re.DOTALL | re.IGNORECASE)
        if title_tag:
            parts.append(f"Title: {html_mod.unescape(title_tag.group(1).strip())}")
        # meta name="description"
        meta_desc = re.search(
            r'<meta\s+[^>]*name=["\']description["\']\s+content="([^"]*)"',
            html_src, re.IGNORECASE,
        )
        if meta_desc:
            parts.append(f"Description: {html_mod.unescape(meta_desc.group(1))}")
        # og:title, og:description, twitter:title, twitter:description
        for prop in ("og:title", "og:description", "twitter:title", "twitter:description"):
            m = re.search(
                rf'<meta\s+[^>]*(?:property|name)=["\'{prop}["\']\s*[^>]*content="([^"]*)"',
                html_src, re.IGNORECASE,
            )
            if not m:
                m = re.search(
                    rf'<meta\s+[^>]*content="([^"]*)"[^>]*(?:property|name)=["\'{prop}["\']',
                    html_src, re.IGNORECASE,
                )
            if m and m.group(1).strip():
                parts.append(f"{prop}: {html_mod.unescape(m.group(1).strip())}")
        return " ".join(parts)

    def _extract_amazon_specific(html_src: str) -> str:
        """Amazon-specific extraction from feature bullets and product title."""
        parts: list[str] = []
        title_match = re.search(
            r'<span[^>]+id="productTitle"[^>]*>(.*?)</span>',
            html_src, re.DOTALL | re.IGNORECASE,
        )
        if title_match:
            parts.append(f"Product: {title_match.group(1).strip()}")
        bullets = re.findall(
            r'<span class="a-list-item"[^>]*>\s*(.*?)\s*</span>',
            html_src, re.DOTALL | re.IGNORECASE,
        )
        bullet_text = " ".join(
            re.sub(r"<[^>]+>", "", b).strip()
            for b in bullets if len(re.sub(r"<[^>]+>", "", b).strip()) > 10
        )
        if bullet_text:
            parts.append(f"Features: {bullet_text}")
        return " ".join(parts)

    # Assemble structured text from all available sources
    structured_text += _extract_ld_json_product(html)
    structured_text += " " + _extract_meta_tags(html)
    if is_amazon:
        structured_text += " " + _extract_amazon_specific(html)

    # ── Detect bot-blocked / thin pages ─────────────────────────────────
    block_signals = [
        "continue shopping" in text.lower() and is_amazon,
        "robot" in text.lower() and "captcha" in text.lower(),
        "sorry, we just need to make sure you" in text.lower(),
        "enter the characters you see below" in text.lower(),
        is_amazon and len(text) < 500 and "Amazon" in text,
    ]
    page_is_blocked = any(block_signals)

    # ALWAYS prepend structured data (ld+json, meta) at the front.
    # This ensures GLiNER and Claude see clean product info first,
    # before any JS garbage that survives tag stripping.
    structured_clean = structured_text.strip()
    if structured_clean:
        logger.info(f"Prepending {len(structured_clean)} chars of structured data")
        text = structured_clean + "\n\n" + text

    # Extra cleanup: remove common JS artifacts that survive tag stripping
    # (inline event handlers, data attributes that leaked, etc.)
    text = re.sub(r'\b(document|window|function|var|const|let|return|querySelector|addEventListener)\b[^.]*?[;{}]', ' ', text)
    text = re.sub(r'\{[^}]{0,200}\}', ' ', text)  # small JSON-like fragments
    text = re.sub(r'//[^\n]*', ' ', text)           # JS single-line comments
    text = re.sub(r'\s+', ' ', text).strip()

    # ── Jina Reader fallback for truly blocked pages ──────────────────
    if page_is_blocked or len(text.strip()) < 200:
        logger.info("Page text is thin/blocked, trying Jina Reader fallback...")
        try:
            async with httpx.AsyncClient(timeout=25, verify=False) as jina_client:
                jina_resp = await jina_client.get(
                    f"https://r.jina.ai/{data.url}",
                    headers={
                        "Accept": "text/plain",
                        "X-Return-Format": "text",
                    },
                )
                if jina_resp.status_code == 200 and len(jina_resp.text.strip()) > 100:
                    jina_text = jina_resp.text.strip()
                    logger.info(f"Jina Reader returned {len(jina_text)} chars")
                    text = jina_text[:8000]
                    page_is_blocked = False
        except Exception as jina_err:
            logger.warning(f"Jina Reader fallback failed: {jina_err}")

    # If STILL thin after all fallbacks, give a helpful error
    if len(text.strip()) < 50:
        site_name = "Amazon" if is_amazon else "This site"
        raise HTTPException(
            400,
            f"{site_name} blocked our request (anti-bot protection). "
            "Try one of these alternatives:\n"
            "1. Use the direct brand website URL (e.g. cerave.com instead of amazon.com/cerave)\n"
            "2. Use Smart Chat mode to describe your product manually\n"
            "3. Copy the product description from the listing and paste it in chat"
        )

    text = text[:8000]

    if not text or len(text) < 20:
        raise HTTPException(400, "Could not extract meaningful text from URL")

    # ── Step 2: GLiNER FIRST — extract grounded entity spans ─────────────
    # GLiNER is the PRIMARY extraction engine. It returns spans that
    # ACTUALLY EXIST in the source text — no hallucination possible.
    # We run multiple passes with focused label sets for deeper extraction.

    gliner_entities: list[dict] = []
    gliner_tone: dict[str, float] = {}
    try:
        # Pass 1: Core product entities
        core_entities = await GLiNERService.extract_entities(
            text[:4000],
            labels=[
                "product name", "brand", "ingredient",
                "pain point", "benefit", "target audience",
                "price", "competitor", "key feature",
            ],
            threshold=0.3,
        )
        gliner_entities.extend(core_entities)

        # Pass 2: Marketing-specific entities (different labels = different extractions)
        marketing_entities = await GLiNERService.extract_entities(
            text[:4000],
            labels=[
                "unique selling point", "testimonial",
                "clinical claim", "usage instruction",
                "product variant", "certification",
            ],
            threshold=0.4,
        )
        gliner_entities.extend(marketing_entities)

        # Pass 3: Zero-shot tone classification
        gliner_tone = await GLiNERService.classify_text(
            text[:2000],
            labels=["premium", "budget", "natural", "clinical", "fun", "serious"],
        )

        logger.info(
            "GLiNER extracted %d entities across 2 passes",
            len(gliner_entities),
        )
    except Exception as e:
        logger.warning("GLiNER extraction failed (will rely on Claude): %s", e)

    # Group GLiNER entities by label
    gliner_grouped: dict[str, list[str]] = {}
    for ent in gliner_entities:
        label = ent.get("label", "").replace(" ", "_")
        val = ent.get("text", "")
        if val and len(val) > 1:
            gliner_grouped.setdefault(label, []).append(val)

    # Deduplicate within each label group (preserve order)
    for label in gliner_grouped:
        seen: set[str] = set()
        deduped: list[str] = []
        for v in gliner_grouped[label]:
            if v.lower() not in seen:
                seen.add(v.lower())
                deduped.append(v)
        gliner_grouped[label] = deduped

    # ── Step 3: Claude SECOND — synthesize from GLiNER's grounded spans ──
    # Claude's job is NOT to extract entities (GLiNER did that).
    # Claude's job is to:
    #   1. Write a coherent product description from the grounded entities
    #   2. Infer target audience reasoning (GLiNER finds WHO, Claude explains WHY)
    #   3. Fill semantic gaps GLiNER can't catch (e.g. implied benefits)
    claude_synthesis: dict[str, Any] = {}
    try:
        gliner_summary = json.dumps(gliner_grouped, indent=2)
        claude_client = ClaudeService._get_client()
        claude_msg = await claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=(
                "You are a product analyst. You are given:\n"
                "1. Raw text scraped from a product page\n"
                "2. Entities already extracted by an NER model (GLiNER)\n\n"
                "Your job is to SYNTHESIZE the extracted entities into a coherent "
                "profile. Do NOT re-extract entities — use what GLiNER found as your "
                "primary source of truth. GLiNER's extractions are grounded in the "
                "actual page text, so trust them.\n\n"
                "Your specific tasks:\n"
                "- Write a clear 2-3 sentence product description using the extracted entities\n"
                "- Infer the target audience and explain WHY (based on pain points + benefits)\n"
                "- Identify the product category\n"
                "- Add any IMPLICIT benefits or pain points that GLiNER's spans might miss\n"
                "- Determine the brand tone\n\n"
                "Respond with ONLY valid JSON:\n"
                '{\n'
                '  "product_description": "2-3 sentence description",\n'
                '  "target_audience": "who and why",\n'
                '  "category": "product category",\n'
                '  "additional_pain_points": ["implied problems not in entity list"],\n'
                '  "additional_benefits": ["implied benefits not in entity list"],\n'
                '  "tone": "premium | budget | natural | clinical | fun | serious",\n'
                '  "marketing_angle": "suggested marketing angle for social media"\n'
                "}\n\n"
                "Keep it grounded. Don't invent features that aren't supported by the text."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"=== EXTRACTED ENTITIES (from GLiNER) ===\n{gliner_summary}\n\n"
                    f"=== RAW PAGE TEXT (first 4000 chars) ===\n{text[:4000]}"
                ),
            }],
        )
        raw = claude_msg.content[0].text.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            claude_synthesis = json.loads(json_match.group())
    except Exception as e:
        logger.warning("Claude synthesis failed (using GLiNER entities only): %s", e)

    # ── Step 4: Build final profile — GLiNER entities are primary ────────
    # GLiNER extractions take priority (grounded). Claude fills gaps.
    product_name = (
        (gliner_grouped.get("product_name", [None])[0])
        or (gliner_grouped.get("brand", [None])[0])
        or "Product"
    )

    brand = (
        gliner_grouped.get("brand", [""])[0]
        if gliner_grouped.get("brand")
        else ""
    )

    product_description = (
        claude_synthesis.get("product_description")
        or text[:500]
    )

    target_audience = (
        claude_synthesis.get("target_audience", "")
        or ", ".join(gliner_grouped.get("target_audience", []))
    )

    # Merge pain points: GLiNER's grounded spans + Claude's inferred ones
    pain_points = gliner_grouped.get("pain_point", [])
    additional_pains = claude_synthesis.get("additional_pain_points", [])
    for p in additional_pains:
        if p.lower() not in {x.lower() for x in pain_points}:
            pain_points.append(p)

    # Merge benefits
    benefits = gliner_grouped.get("benefit", [])
    additional_benefits = claude_synthesis.get("additional_benefits", [])
    for b in additional_benefits:
        if b.lower() not in {x.lower() for x in benefits}:
            benefits.append(b)

    key_features = gliner_grouped.get("key_feature", []) + gliner_grouped.get("unique_selling_point", [])
    ingredients = gliner_grouped.get("ingredient", [])

    # Determine tone — combine GLiNER classification with Claude's assessment
    tone = claude_synthesis.get("tone", "")
    if gliner_tone and not tone:
        tone = max(gliner_tone, key=gliner_tone.get) if gliner_tone else ""

    # ── Step 5: Build campaign entity schema for downstream use ──────────
    profile_for_schema = {
        "product_name": product_name,
        "category": claude_synthesis.get("category", ""),
        "pain_points": pain_points,
        "benefits": benefits,
        "ingredients": ingredients,
        "grouped": gliner_grouped,
    }
    campaign_schema = GLiNERService.build_campaign_schema(profile_for_schema)

    return {
        "product_name": product_name,
        "product_description": product_description,
        "target_audience": target_audience,
        "extracted_entities": {
            "product_name": product_name,
            "category": claude_synthesis.get("category", ""),
            "target_audience": [target_audience] if target_audience else [],
            "pain_points": pain_points,
            "benefits": benefits,
            "key_features": key_features,
            "ingredients": ingredients,
            "brand": brand,
            "tone": tone,
            "competitors": gliner_grouped.get("competitor", []),
            "pricing": gliner_grouped.get("price", []),
            "certifications": gliner_grouped.get("certification", []),
            "usage_instructions": gliner_grouped.get("usage_instruction", []),
            "clinical_claims": gliner_grouped.get("clinical_claim", []),
            "testimonials": gliner_grouped.get("testimonial", []),
            "product_variants": gliner_grouped.get("product_variant", []),
            "marketing_angle": claude_synthesis.get("marketing_angle", ""),
        },
        "campaign_schema": campaign_schema,
        "source_url": data.url,
        "extraction_method": "gliner_primary_claude_synthesis",
        "gliner_raw": gliner_entities[:30],
        "gliner_tone_scores": gliner_tone,
    }


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]


@router.post("/chat")
async def chat_campaign(data: ChatRequest):
    """Smart chat interface for building campaigns."""
    conversation = "\n".join([
        f"{msg['role']}: {msg['content']}"
        for msg in data.messages
    ])

    system_prompt = """You are a helpful assistant helping users create marketing campaigns.
    
Your job:
1. Ask smart, progressive questions about their product
2. Extract product information from their answers
3. When you have enough info (product name, description, target audience), 
   output a JSON object with the campaign data

Output format when ready:
{
  "response": "Your conversational response",
  "campaign_data": {
    "name": "Campaign name",
    "product_name": "...",
    "product_description": "...",
    "target_audience": "...",
    "platforms": ["twitter", "reddit", "instagram"]
  }
}

If not ready yet, just return:
{
  "response": "Your next question or response",
  "campaign_data": null
}
"""

    try:
        client = ClaudeService._get_client()
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": conversation}
            ],
        )

        response_text = message.content[0].text.strip()

        try:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "response": parsed.get("response", response_text),
                    "campaign_data": parsed.get("campaign_data"),
                }
        except Exception:
            pass

        return {
            "response": response_text,
            "campaign_data": None,
        }
    except Exception as e:
        raise HTTPException(500, f"Chat failed: {str(e)}")


# ── Standard CRUD & lifecycle (dynamic /{campaign_id} routes) ────────────


@router.post("/", response_model=dict)
async def create_campaign(data: CampaignCreate):
    """Create a new campaign.

    The campaign is registered immediately and returned to the frontend.
    The full agent pipeline (intent → scout → vision → strategy → execute)
    is launched in the background so the user doesn't have to wait.
    """
    import asyncio
    import logging
    _logger = logging.getLogger("create_campaign")

    campaign_id = uuid.uuid4().hex

    # Use pre-extracted data if available (from /from-link or /chat)
    pre_entities = data.extracted_entities or {}
    pre_schema = data.campaign_schema or {}

    # Register the campaign immediately WITH extracted data
    _campaigns[campaign_id] = {
        "id": campaign_id,
        "name": data.name,
        "product_name": data.product_name,
        "product_description": data.product_description,
        "target_audience": data.target_audience,
        "platforms": data.platforms,
        "status": CampaignStatus.ACTIVE,
        "pain_points": pre_entities.get("pain_points", []),
        "benefits": pre_entities.get("benefits", []),
        "extracted_entities": pre_entities,
        "campaign_schema": pre_schema,
        "gliner_raw": data.gliner_raw or [],
        "product_knowledge": {},
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "first_cycle_result": None,
        # Pipeline status tracking — frontend polls this
        "pipeline_status": {
            "stage": "starting",
            "stages_completed": [],
            "current_agent": None,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "error": None,
        },
    }

    # Launch the full pipeline in the background
    async def _run_pipeline():
        pipeline_status = _campaigns[campaign_id]["pipeline_status"]

        def _update_stage(stage: str, agent: str | None = None):
            if stage != pipeline_status["stage"]:
                prev = pipeline_status["stage"]
                if prev and prev not in ("starting", "completed", "error"):
                    if prev not in pipeline_status["stages_completed"]:
                        pipeline_status["stages_completed"].append(prev)
            pipeline_status["stage"] = stage
            pipeline_status["current_agent"] = agent

        try:
            _logger.info("Background pipeline starting for campaign %s", campaign_id)

            _update_stage("intent", "Intent Agent")
            _logger.info("[%s] Running Intent Agent...", campaign_id)

            # Wrap in try so each stage can fail gracefully
            result: dict[str, Any] = {}
            try:
                result = await SwarmCoordinator.launch_campaign(data)
            except Exception as stage_err:
                _logger.error("[%s] Pipeline stage failed: %s", campaign_id, stage_err)
                pipeline_status["error"] = f"Pipeline error: {str(stage_err)[:200]}"

            # Mark all stages as completed (SwarmCoordinator runs them all)
            for s in ["intent", "scouting", "vision", "strategy", "engagement"]:
                if s not in pipeline_status["stages_completed"]:
                    pipeline_status["stages_completed"].append(s)

            pipeline_status["stage"] = "completed"
            pipeline_status["current_agent"] = None
            pipeline_status["completed_at"] = datetime.utcnow().isoformat()

            # Update the campaign with pipeline results (merge with pre-extracted)
            pipeline_entities = (
                result.get("intent", {})
                .get("extracted_entities", {})
            )
            merged_entities = {**pre_entities}
            for k, v in pipeline_entities.items():
                if v and (not merged_entities.get(k) or merged_entities.get(k) == []):
                    merged_entities[k] = v

            _campaigns[campaign_id].update({
                "pain_points": merged_entities.get("pain_points", pre_entities.get("pain_points", [])),
                "benefits": merged_entities.get("benefits", pre_entities.get("benefits", [])),
                "extracted_entities": merged_entities,
                "product_knowledge": result.get("intent", {}).get("product_knowledge", {}),
                "updated_at": datetime.utcnow().isoformat(),
                "first_cycle_result": result if result else None,
            })
            _logger.info("Background pipeline completed for campaign %s", campaign_id)
        except Exception as e:
            _logger.error("Background pipeline failed for campaign %s: %s", campaign_id, e)
            pipeline_status["stage"] = "error"
            pipeline_status["current_agent"] = None
            pipeline_status["error"] = str(e)[:200]
            # Keep campaign active — extracted data is still valid

    asyncio.create_task(_run_pipeline())

    return {
        "campaign_id": campaign_id,
        "status": "active",
        "message": "Campaign created. Agent pipeline is running in the background.",
    }


@router.get("/")
async def list_campaigns():
    """List all campaigns."""
    active = SwarmCoordinator.get_active_campaigns()
    stored = list(_campaigns.values())

    return {
        "campaigns": stored,
        "active_swarms": active,
    }


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get campaign details."""
    if campaign_id not in _campaigns:
        raise HTTPException(404, "Campaign not found")
    return _campaigns[campaign_id]


@router.post("/{campaign_id}/cycle")
async def trigger_cycle(campaign_id: str):
    """Manually trigger a new pipeline cycle for a campaign."""
    try:
        result = await SwarmCoordinator.run_cycle(campaign_id)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{campaign_id}/learn")
async def trigger_learning(campaign_id: str):
    """Manually trigger a learning cycle."""
    result = await SwarmCoordinator.run_learning(campaign_id)
    return result


@router.post("/{campaign_id}/collect-metrics")
async def trigger_metrics(campaign_id: str):
    """Manually trigger metrics collection."""
    result = await SwarmCoordinator.run_metrics_collection(campaign_id)
    return result


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause a campaign's autonomous cycles."""
    if SwarmCoordinator.pause_campaign(campaign_id):
        if campaign_id in _campaigns:
            _campaigns[campaign_id]["status"] = CampaignStatus.PAUSED
        return {"status": "paused"}
    raise HTTPException(404, "Campaign not found in active swarm")


@router.post("/{campaign_id}/resume")
async def resume_campaign(campaign_id: str):
    """Resume a paused campaign."""
    if SwarmCoordinator.resume_campaign(campaign_id):
        if campaign_id in _campaigns:
            _campaigns[campaign_id]["status"] = CampaignStatus.ACTIVE
        return {"status": "active"}
    raise HTTPException(404, "Campaign not found in active swarm")
