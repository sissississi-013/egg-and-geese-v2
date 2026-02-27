"""Neo4j node/relationship schema definitions and helpers."""

from __future__ import annotations

from typing import Any

from app.services.neo4j_service import Neo4jService


async def create_campaign_node(
    campaign_id: str,
    name: str,
    product_name: str,
    target_audience: str,
) -> None:
    await Neo4jService.run_write(
        """
        MERGE (c:Campaign {id: $id})
        SET c.name = $name,
            c.product_name = $product_name,
            c.target_audience = $target_audience,
            c.created_at = datetime()
        """,
        {
            "id": campaign_id,
            "name": name,
            "product_name": product_name,
            "target_audience": target_audience,
        },
    )


async def create_product_node(
    product_id: str,
    name: str,
    category: str,
    benefits: list[str],
    pain_points_solved: list[str],
    ingredients: list[str],
) -> None:
    await Neo4jService.run_write(
        """
        MERGE (p:Product {id: $id})
        SET p.name = $name,
            p.category = $category,
            p.benefits = $benefits,
            p.pain_points_solved = $pain_points_solved,
            p.ingredients = $ingredients
        """,
        {
            "id": product_id,
            "name": name,
            "category": category,
            "benefits": benefits,
            "pain_points_solved": pain_points_solved,
            "ingredients": ingredients,
        },
    )


async def link_campaign_to_product(
    campaign_id: str, product_id: str
) -> None:
    await Neo4jService.run_write(
        """
        MATCH (c:Campaign {id: $cid}), (p:Product {id: $pid})
        MERGE (c)-[:TARGETS]->(p)
        """,
        {"cid": campaign_id, "pid": product_id},
    )


async def link_campaign_to_platform(
    campaign_id: str, platform: str
) -> None:
    await Neo4jService.run_write(
        """
        MATCH (c:Campaign {id: $cid}), (pl:Platform {name: $platform})
        MERGE (c)-[:ACTIVE_ON]->(pl)
        """,
        {"cid": campaign_id, "platform": platform},
    )


async def create_scouted_post_node(
    post_id: str,
    platform: str,
    url: str,
    text: str,
    visual_context: str | None,
    relevance_score: float,
    product_id: str | None = None,
) -> None:
    await Neo4jService.run_write(
        """
        MERGE (sp:ScoutedPost {id: $id})
        SET sp.platform = $platform,
            sp.url = $url,
            sp.text = $text,
            sp.visual_context = $visual_context,
            sp.relevance_score = $relevance_score,
            sp.discovered_at = datetime()
        WITH sp
        MATCH (pl:Platform {name: $platform})
        MERGE (sp)-[:ON_PLATFORM]->(pl)
        """,
        {
            "id": post_id,
            "platform": platform,
            "url": url,
            "text": text,
            "visual_context": visual_context or "",
            "relevance_score": relevance_score,
        },
    )

    if product_id:
        await Neo4jService.run_write(
            """
            MATCH (sp:ScoutedPost {id: $post_id}), (p:Product {id: $product_id})
            MERGE (sp)-[:DISCUSSES]->(p)
            """,
            {"post_id": post_id, "product_id": product_id},
        )


async def create_engagement_node(
    engagement_id: str,
    post_id: str,
    action_type: str,
    content: str,
    strategy_id: str,
) -> None:
    await Neo4jService.run_write(
        """
        MERGE (e:Engagement {id: $id})
        SET e.action_type = $action_type,
            e.content = $content,
            e.timestamp = datetime()
        WITH e
        MATCH (sp:ScoutedPost {id: $post_id})
        MERGE (e)-[:ON_POST]->(sp)
        """,
        {
            "id": engagement_id,
            "action_type": action_type,
            "content": content,
            "post_id": post_id,
        },
    )

    # Link to strategy
    await Neo4jService.run_write(
        """
        MATCH (e:Engagement {id: $eid}), (s:Strategy {id: $sid})
        MERGE (e)-[:USED_STRATEGY]->(s)
        """,
        {"eid": engagement_id, "sid": strategy_id},
    )


async def create_strategy_node(
    strategy_id: str,
    style: str,
    tone: str,
    template_type: str,
    confidence_score: float = 0.5,
    parent_strategy_id: str | None = None,
) -> None:
    await Neo4jService.run_write(
        """
        MERGE (s:Strategy {id: $id})
        SET s.style = $style,
            s.tone = $tone,
            s.template_type = $template_type,
            s.confidence_score = $confidence_score,
            s.created_at = datetime()
        """,
        {
            "id": strategy_id,
            "style": style,
            "tone": tone,
            "template_type": template_type,
            "confidence_score": confidence_score,
        },
    )

    if parent_strategy_id:
        await Neo4jService.run_write(
            """
            MATCH (s:Strategy {id: $sid}), (parent:Strategy {id: $pid})
            MERGE (s)-[:EVOLVED_FROM]->(parent)
            """,
            {"sid": strategy_id, "pid": parent_strategy_id},
        )


async def update_strategy_confidence(
    strategy_id: str, new_score: float
) -> None:
    await Neo4jService.run_write(
        """
        MATCH (s:Strategy {id: $id})
        SET s.confidence_score = $score,
            s.updated_at = datetime()
        """,
        {"id": strategy_id, "score": new_score},
    )
