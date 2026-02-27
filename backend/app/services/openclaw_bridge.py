"""HTTP bridge to the OpenClaw Node.js execution gateway."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class OpenClawBridge:
    """Sends execution commands to the OpenClaw gateway over HTTP.

    The gateway handles the actual browser-automation / API calls to
    Twitter, Reddit, and Instagram.
    """

    BASE_URL = settings.openclaw_gateway_url

    @classmethod
    async def post_comment(
        cls,
        platform: str,
        post_url: str,
        comment_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Instruct the gateway to post a comment on a social media post.

        Returns:
            Gateway response with platform_post_id and status.
        """
        payload = {
            "action": "comment",
            "platform": platform,
            "post_url": post_url,
            "content": comment_text,
            "metadata": metadata or {},
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/api/execute",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def post_reply(
        cls,
        platform: str,
        post_url: str,
        parent_comment_id: str,
        reply_text: str,
    ) -> dict[str, Any]:
        """Reply to an existing comment on a post."""
        payload = {
            "action": "reply",
            "platform": platform,
            "post_url": post_url,
            "parent_comment_id": parent_comment_id,
            "content": reply_text,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/api/execute",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def repost(
        cls,
        platform: str,
        post_url: str,
        quote_text: str | None = None,
    ) -> dict[str, Any]:
        """Repost / retweet / share a post, optionally with quote text."""
        payload = {
            "action": "repost",
            "platform": platform,
            "post_url": post_url,
            "content": quote_text or "",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/api/execute",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def collect_metrics(
        cls,
        platform: str,
        post_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Ask the gateway to scrape current metrics for specific posts."""
        payload = {
            "action": "collect_metrics",
            "platform": platform,
            "post_ids": post_ids,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/api/metrics",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json().get("metrics", [])

    @classmethod
    async def health_check(cls) -> bool:
        """Check if the gateway is alive."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{cls.BASE_URL}/api/health")
                return resp.status_code == 200
        except Exception:
            return False
