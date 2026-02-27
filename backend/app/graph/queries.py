"""Reusable Cypher query templates for the knowledge graph."""

# ---------------------------------------------------------------------------
# Campaign queries
# ---------------------------------------------------------------------------
GET_CAMPAIGN_GRAPH = """
MATCH (c:Campaign {id: $campaign_id})
OPTIONAL MATCH (c)-[:TARGETS]->(p:Product)
OPTIONAL MATCH (c)-[:ACTIVE_ON]->(pl:Platform)
RETURN c, collect(DISTINCT p) AS products, collect(DISTINCT pl) AS platforms
"""

# ---------------------------------------------------------------------------
# Scouted post queries
# ---------------------------------------------------------------------------
GET_UNENGAGED_POSTS = """
MATCH (c:Campaign {id: $campaign_id})-[:TARGETS]->(p:Product)
      <-[:DISCUSSES]-(sp:ScoutedPost)
WHERE NOT (sp)<-[:ON_POST]-(:Engagement)
RETURN sp
ORDER BY sp.relevance_score DESC
LIMIT $limit
"""

GET_POSTS_BY_PLATFORM = """
MATCH (sp:ScoutedPost)-[:ON_PLATFORM]->(pl:Platform {name: $platform})
WHERE sp.relevance_score >= $min_score
RETURN sp
ORDER BY sp.discovered_at DESC
LIMIT $limit
"""

# ---------------------------------------------------------------------------
# Engagement & metrics queries
# ---------------------------------------------------------------------------
GET_ENGAGEMENT_HISTORY = """
MATCH (c:Campaign {id: $campaign_id})-[:TARGETS]->(:Product)
      <-[:DISCUSSES]-(:ScoutedPost)<-[:ON_POST]-(e:Engagement)
      -[:USED_STRATEGY]->(s:Strategy)
OPTIONAL MATCH (e)-[:HAS_METRICS]->(m:MetricsSnapshot)
RETURN e.id AS engagement_id,
       e.action_type AS action_type,
       e.content AS content,
       e.timestamp AS timestamp,
       s.id AS strategy_id,
       s.style AS style,
       s.tone AS tone,
       m.impressions AS impressions,
       m.likes AS likes,
       m.replies AS replies
ORDER BY e.timestamp DESC
LIMIT $limit
"""

TOP_STRATEGIES = """
MATCH (e:Engagement)-[:USED_STRATEGY]->(s:Strategy)
OPTIONAL MATCH (e)-[:HAS_METRICS]->(m:MetricsSnapshot)
WITH s,
     avg(m.impressions) AS avg_impressions,
     avg(m.likes) AS avg_likes,
     count(e) AS usage_count
WHERE usage_count >= $min_usage
RETURN s.id AS strategy_id,
       s.style AS style,
       s.tone AS tone,
       s.confidence_score AS confidence,
       avg_impressions,
       avg_likes,
       usage_count
ORDER BY avg_impressions DESC
LIMIT $limit
"""

# ---------------------------------------------------------------------------
# Strategy evolution queries
# ---------------------------------------------------------------------------
STRATEGY_EVOLUTION_CHAIN = """
MATCH path = (s:Strategy {id: $strategy_id})-[:EVOLVED_FROM*0..10]->(ancestor:Strategy)
RETURN [node IN nodes(path) |
        {id: node.id, style: node.style, tone: node.tone,
         confidence: node.confidence_score}] AS chain
"""

# ---------------------------------------------------------------------------
# Activity feed (latest agent actions)
# ---------------------------------------------------------------------------
RECENT_ACTIVITY = """
MATCH (e:Engagement)-[:ON_POST]->(sp:ScoutedPost)-[:ON_PLATFORM]->(pl:Platform)
OPTIONAL MATCH (e)-[:USED_STRATEGY]->(s:Strategy)
OPTIONAL MATCH (e)-[:HAS_METRICS]->(m:MetricsSnapshot)
RETURN e.id AS id,
       e.action_type AS action_type,
       e.content AS content,
       e.timestamp AS timestamp,
       sp.url AS post_url,
       sp.text AS post_text,
       pl.name AS platform,
       s.style AS strategy_style,
       m.impressions AS latest_impressions,
       m.likes AS latest_likes
ORDER BY e.timestamp DESC
LIMIT $limit
"""

# ---------------------------------------------------------------------------
# Knowledge graph overview (for visualization)
# ---------------------------------------------------------------------------
FULL_GRAPH_OVERVIEW = """
MATCH (c:Campaign {id: $campaign_id})
OPTIONAL MATCH (c)-[r1:TARGETS]->(p:Product)
OPTIONAL MATCH (c)-[r2:ACTIVE_ON]->(pl:Platform)
OPTIONAL MATCH (sp:ScoutedPost)-[r3:DISCUSSES]->(p)
OPTIONAL MATCH (e:Engagement)-[r4:ON_POST]->(sp)
OPTIONAL MATCH (e)-[r5:USED_STRATEGY]->(s:Strategy)
OPTIONAL MATCH (s)-[r6:EVOLVED_FROM]->(s2:Strategy)
RETURN c, p, pl, sp, e, s, s2,
       r1, r2, r3, r4, r5, r6
LIMIT 200
"""
