"""Anthropic Claude client for agent reasoning and humanized comment generation."""

from __future__ import annotations

from typing import Any

import anthropic

from app.config import settings


class ClaudeService:
    """Wraps the Anthropic Python SDK for the Strategy Engine."""

    _client: anthropic.AsyncAnthropic | None = None

    @classmethod
    def _get_client(cls) -> anthropic.AsyncAnthropic:
        if cls._client is None:
            cls._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
            )
        return cls._client

    @classmethod
    async def generate_comment(
        cls,
        post_context: str,
        product_info: str,
        visual_context: str | None = None,
        strategy_hints: str | None = None,
        tone: str = "casual and authentic",
    ) -> str:
        """Generate a humanized comment/reply for a social media post.

        Args:
            post_context: The original post text + metadata.
            product_info: Verified product details from Senso.
            visual_context: Reka Vision analysis of post media (optional).
            strategy_hints: Guidance from the learning loop (optional).
            tone: Desired comment tone.

        Returns:
            The generated comment text ready to post.
        """
        system_prompt = (
            "You are a social media marketing agent disguised as a regular user. "
            "Your job is to write authentic, humanized comments that naturally "
            "recommend a product in response to relevant discussions. "
            "Rules:\n"
            "- Sound like a real person sharing genuine experience\n"
            "- Reference specific product benefits that match the post's problem\n"
            "- NEVER use marketing language or sound like an ad\n"
            "- Be empathetic and relatable\n"
            "- Keep it concise (1-3 sentences max)\n"
            "- Include minor imperfections (casual grammar, lowercase, etc.)\n"
            "- NEVER make unsupported health/medical claims\n"
        )

        user_msg = f"""Post to reply to:
{post_context}

Product information (verified):
{product_info}
"""
        if visual_context:
            user_msg += f"\nVisual context from the post's image/video:\n{visual_context}\n"

        if strategy_hints:
            user_msg += f"\nStrategy guidance (from past performance data):\n{strategy_hints}\n"

        user_msg += (
            f"\nDesired tone: {tone}\n"
            "\nGenerate ONE authentic comment. Output ONLY the comment text, nothing else."
        )

        client = cls._get_client()
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        return message.content[0].text.strip()

    @classmethod
    async def generate_strategy(
        cls,
        campaign_context: str,
        historical_performance: str,
        available_posts: str,
    ) -> dict[str, Any]:
        """Decide which posts to engage with and how.

        Returns a structured action plan as a dict.
        """
        system_prompt = (
            "You are a strategic marketing AI. Analyze the campaign context, "
            "historical performance data, and available posts. Decide:\n"
            "1. Which posts to prioritize (rank by potential impact)\n"
            "2. What engagement type for each (comment, reply, repost)\n"
            "3. What tone/style to use (based on what worked before)\n"
            "4. Any new experimental approaches to try\n\n"
            "Output valid JSON with this structure:\n"
            '{"actions": [{"post_id": "...", "action_type": "comment|reply|repost", '
            '"tone": "...", "key_points": ["..."], "experimental": false}], '
            '"reasoning": "...", "strategy_id": "..."}'
        )

        client = cls._get_client()
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Campaign:\n{campaign_context}\n\n"
                        f"Historical performance:\n{historical_performance}\n\n"
                        f"Available posts:\n{available_posts}"
                    ),
                }
            ],
        )

        import json

        text = message.content[0].text.strip()
        # Try to extract JSON from the response
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # If Claude wrapped it in markdown fences
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
                return json.loads(text)
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                return json.loads(text)
            return {"actions": [], "reasoning": text, "strategy_id": "fallback"}

    @classmethod
    async def analyze_performance(
        cls,
        metrics_summary: str,
    ) -> dict[str, Any]:
        """Analyze collected metrics and suggest strategy adjustments.

        Returns insights and recommended changes.
        """
        system_prompt = (
            "You are a marketing analytics AI. Analyze the engagement metrics "
            "and identify patterns. Output JSON with:\n"
            '{"insights": ["..."], "top_performing_styles": ["..."], '
            '"underperforming_styles": ["..."], '
            '"recommended_changes": ["..."], '
            '"confidence_adjustments": {"strategy_id": new_score}}'
        )

        client = cls._get_client()
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Metrics data:\n{metrics_summary}"}
            ],
        )

        import json

        text = message.content[0].text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
                return json.loads(text)
            return {"insights": [text], "recommended_changes": []}
