"""Scheduler — APScheduler-based cron for periodic heartbeats.

Triggers metrics collection and learning cycles at configured
intervals (default: every 30 minutes).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.orchestrator.swarm import SwarmCoordinator

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _heartbeat_job() -> None:
    """Scheduled job: runs a full heartbeat across all campaigns."""
    logger.info("Scheduler: heartbeat triggered")
    try:
        results = await SwarmCoordinator.run_full_heartbeat()
        active = len(results)
        logger.info("Scheduler: heartbeat complete — %d campaigns processed", active)
    except Exception as e:
        logger.error("Scheduler: heartbeat failed: %s", e)


def start_scheduler() -> None:
    """Start the background scheduler."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _heartbeat_job,
        trigger=IntervalTrigger(
            minutes=settings.metrics_poll_interval_minutes
        ),
        id="swarm_heartbeat",
        name="Swarm Heartbeat",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — heartbeat every %d minutes",
        settings.metrics_poll_interval_minutes,
    )


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
