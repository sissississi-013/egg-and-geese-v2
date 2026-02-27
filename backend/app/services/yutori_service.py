"""Yutori API client for web-agent-powered social media scouting.

Yutori (https://docs.yutori.com) is a web-agent platform with four APIs:
  - n1:       Pixels-to-actions LLM for browser control
  - Browsing: One-time cloud browser automation
  - Research: Deep one-time web research
  - Scouting: Continuous scheduled web monitoring

We primarily use the **Scouting API** to monitor social media and web
for discussions related to a campaign's target problem, and the
**Research API** for one-off deep-dives.

Auth: X-API-Key header.  Keys start with 'yt_'.
Base URL: https://api.yutori.com
Pricing: $0.35 per scout-run.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class YutoriService:
    """Wraps the Yutori Scouting + Research APIs for discovering relevant social posts."""

    BASE_URL = settings.yutori_base_url  # https://api.yutori.com

    @classmethod
    def _headers(cls) -> dict[str, str]:
        return {
            "X-API-Key": settings.yutori_api_key,
            "Content-Type": "application/json",
        }

    # ── Scouting API ─────────────────────────────────────────────

    @classmethod
    async def create_scout(
        cls,
        query: str,
        output_interval: int = 86400,
        webhook_url: str | None = None,
        output_schema: dict[str, Any] | None = None,
        user_timezone: str = "America/Los_Angeles",
        skip_email: bool = True,
    ) -> dict[str, Any]:
        """Create a new Scout — a continuously-running web monitor.

        The scout will spin up sub-agents to periodically search the web
        for content matching `query` and alert via webhook/updates endpoint.

        Args:
            query: Natural-language description of what to monitor.
                   e.g. "people discussing oily hair problems on Twitter and Reddit"
            output_interval: Seconds between runs (min 1800, default 86400 = daily).
            webhook_url: Optional URL to receive update notifications.
            output_schema: Optional JSON schema for structured output fields.
            user_timezone: Timezone for scheduling.
            skip_email: Whether to skip email notifications (default True).

        Returns:
            Scout metadata including id and status.
        """
        payload: dict[str, Any] = {
            "query": query,
            "output_interval": output_interval,
            "user_timezone": user_timezone,
            "skip_email": skip_email,
        }
        if webhook_url:
            payload["webhook_url"] = webhook_url
            payload["webhook_format"] = "scout"
        if output_schema:
            payload["output_schema"] = output_schema

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/v1/scouting/tasks",
                json=payload,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info("Created Yutori scout: %s", data.get("id"))
            return data

    @classmethod
    async def list_scouts(
        cls,
        page_size: int = 20,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all scouts for the authenticated API key."""
        params: dict[str, Any] = {"page_size": page_size}
        if status:
            params["status"] = status

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{cls.BASE_URL}/v1/scouting/tasks",
                params=params,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            # API may return {"scouts": [...]} or a list directly
            if isinstance(data, list):
                return data
            return data.get("scouts", data.get("results", [data]))

    @classmethod
    async def get_scout_detail(cls, scout_id: str) -> dict[str, Any]:
        """Get full details for a specific scout."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{cls.BASE_URL}/v1/scouting/tasks/{scout_id}",
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def get_scout_updates(
        cls,
        scout_id: str,
        limit: int = 50,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get the latest updates/findings from a scout run.

        Each update contains structured results from the scout's
        web-research sub-agents.

        Returns:
            List of update objects with findings.
        """
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{cls.BASE_URL}/v1/scouting/tasks/{scout_id}/updates",
                params=params,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("updates", data.get("results", []))

    @classmethod
    async def pause_scout(cls, scout_id: str) -> dict[str, Any]:
        """Pause a running scout."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/v1/scouting/tasks/{scout_id}/pause",
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def restart_scout(cls, scout_id: str) -> dict[str, Any]:
        """Resume a paused scout."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/v1/scouting/tasks/{scout_id}/restart",
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def delete_scout(cls, scout_id: str) -> None:
        """Delete a scout permanently."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{cls.BASE_URL}/v1/scouting/tasks/{scout_id}",
                headers=cls._headers(),
            )
            resp.raise_for_status()

    # ── Research API (one-off deep research) ─────────────────────

    @classmethod
    async def create_research_task(
        cls,
        query: str,
        output_schema: dict[str, Any] | None = None,
        user_timezone: str = "America/Los_Angeles",
    ) -> dict[str, Any]:
        """Create a one-time research task.

        Uses 100+ MCP tools for comprehensive web-based research.
        Same infrastructure as Scouting but no recurring schedule.

        Returns:
            Task metadata including task_id.
        """
        payload: dict[str, Any] = {
            "query": query,
            "user_timezone": user_timezone,
        }
        if output_schema:
            payload["output_schema"] = output_schema

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{cls.BASE_URL}/v1/research/tasks",
                json=payload,
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def get_research_result(cls, task_id: str) -> dict[str, Any]:
        """Poll for the result of a research task.

        Returns:
            Task result with status: queued | running | succeeded | failed
        """
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{cls.BASE_URL}/v1/research/tasks/{task_id}",
                headers=cls._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    # ── Helpers ───────────────────────────────────────────────────

    @classmethod
    def updates_to_scouted_posts(
        cls,
        updates: list[dict[str, Any]],
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        """Convert raw Yutori scout updates into our ScoutedPost-like dicts.

        Yutori returns structured research results per update. We normalize
        them into a consistent format for downstream agents.
        """
        posts: list[dict[str, Any]] = []
        for update in updates:
            # Each update may contain multiple findings
            content = update.get("content", update.get("output", ""))
            structured = update.get("structured_output", {})

            posts.append(
                {
                    "campaign_id": campaign_id,
                    "source": "yutori_scout",
                    "update_id": update.get("id", ""),
                    "timestamp": update.get("created_at", ""),
                    "content": content,
                    "structured_data": structured,
                    "raw_update": update,
                }
            )
        return posts
