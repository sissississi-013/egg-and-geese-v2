"""Neo4j driver wrapper and connection management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from app.config import settings


class Neo4jService:
    """Manages the Neo4j async driver lifecycle."""

    _driver: AsyncDriver | None = None

    @classmethod
    async def connect(cls) -> None:
        cls._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify connectivity on AuraDB (requires database param)
        async with cls._driver.session(
            database=settings.neo4j_database
        ) as session:
            await session.run("RETURN 1")

    @classmethod
    async def close(cls) -> None:
        if cls._driver:
            await cls._driver.close()
            cls._driver = None

    @classmethod
    @asynccontextmanager
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        if cls._driver is None:
            await cls.connect()
        assert cls._driver is not None
        async with cls._driver.session(
            database=settings.neo4j_database
        ) as session:
            yield session

    @classmethod
    async def run_query(
        cls, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        async with cls.get_session() as session:
            result = await session.run(query, params or {})
            records = await result.data()
            return records

    @classmethod
    async def run_write(
        cls, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        async with cls.get_session() as session:
            result = await session.run(query, params or {})
            records = await result.data()
            await result.consume()
            return records

    @classmethod
    async def init_constraints(cls) -> None:
        """Create uniqueness constraints and indexes on first boot."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Campaign) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (pl:Platform) REQUIRE pl.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sp:ScoutedPost) REQUIRE sp.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Engagement) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Strategy) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (sp:ScoutedPost) ON (sp.platform)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Engagement) ON (e.timestamp)",
        ]
        for stmt in constraints:
            await cls.run_write(stmt)

        # Seed platform nodes
        for platform in ("twitter", "reddit", "instagram"):
            await cls.run_write(
                "MERGE (p:Platform {name: $name})",
                {"name": platform},
            )
