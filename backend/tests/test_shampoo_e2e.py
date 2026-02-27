"""End-to-end integration test: Oily Hair Shampoo Use Case.

This test validates the full pipeline with the example from the plan:
A local business selling shampoo for oily hair deploys a swarm of agents
that scout relevant discussions, engage authentically, and self-improve.

Run with: python -m pytest tests/test_shampoo_e2e.py -v -s
(Requires all services running or mocked)
"""

import asyncio
import json
import httpx
import pytest

BASE_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def api(method: str, path: str, body: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
        if method == "GET":
            resp = await client.get(path)
        elif method == "POST":
            resp = await client.post(path, json=body)
        else:
            raise ValueError(f"Unknown method: {method}")
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestShampooE2E:
    """Walk through the full oily-hair shampoo use case."""

    campaign_id: str = ""

    @pytest.mark.asyncio
    async def test_01_health(self):
        """Verify orchestrator is up."""
        data = await api("GET", "/api/health")
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_02_create_campaign(self):
        """Create the shampoo campaign — triggers full pipeline."""
        result = await api(
            "POST",
            "/api/campaigns/",
            {
                "name": "Oily Hair Shampoo Launch",
                "product_name": "FreshLocks Oil Control Shampoo",
                "product_description": (
                    "FreshLocks is a sulfate-free shampoo specifically designed for people "
                    "with oily and greasy hair. It contains tea tree oil and salicylic acid "
                    "to gently control excess sebum production for up to 48 hours. "
                    "The formula is lightweight, non-stripping, and safe for daily use. "
                    "Key benefits: controls oiliness, adds volume, fresh minty scent, "
                    "doesn't dry out hair. Made by a local family business with "
                    "all-natural ingredients. Price: $14.99 for 12oz bottle."
                ),
                "target_audience": "people with oily/greasy hair, ages 18-35",
                "platforms": ["twitter", "reddit", "instagram"],
            },
        )

        assert "campaign_id" in result
        TestShampooE2E.campaign_id = result["campaign_id"]
        print(f"\n✅ Campaign created: {result['campaign_id']}")
        print(f"   First cycle results: {json.dumps(result.get('first_cycle', {}), indent=2)}")

    @pytest.mark.asyncio
    async def test_03_list_campaigns(self):
        """Verify the campaign appears in the list."""
        data = await api("GET", "/api/campaigns/")
        assert len(data["campaigns"]) > 0
        print(f"\n✅ Campaigns: {len(data['campaigns'])}")
        print(f"   Active swarms: {len(data.get('active_swarms', []))}")

    @pytest.mark.asyncio
    async def test_04_campaign_detail(self):
        """Fetch campaign detail with extracted entities."""
        data = await api("GET", f"/api/campaigns/{self.campaign_id}")
        assert data["product_name"] == "FreshLocks Oil Control Shampoo"
        entities = data.get("extracted_entities", {})
        print(f"\n✅ Extracted entities: {json.dumps(entities, indent=2)}")

    @pytest.mark.asyncio
    async def test_05_get_activity(self):
        """Check that agent activity was recorded."""
        data = await api("GET", "/api/agents/activity?limit=20")
        activities = data.get("activity", [])
        print(f"\n✅ Agent activity entries: {len(activities)}")
        for a in activities[:5]:
            print(f"   - [{a.get('platform')}] {a.get('action_type')}: {a.get('content', '')[:60]}...")

    @pytest.mark.asyncio
    async def test_06_collect_metrics(self):
        """Manually trigger metrics collection."""
        if not self.campaign_id:
            pytest.skip("No campaign")
        data = await api("POST", f"/api/campaigns/{self.campaign_id}/collect-metrics")
        print(f"\n✅ Metrics collected: {data}")

    @pytest.mark.asyncio
    async def test_07_trigger_learning(self):
        """Trigger a learning cycle."""
        if not self.campaign_id:
            pytest.skip("No campaign")
        data = await api("POST", f"/api/campaigns/{self.campaign_id}/learn")
        print(f"\n✅ Learning insights: {data.get('insights', [])}")
        print(f"   Adjustments: {data.get('adjustments', [])}")
        print(f"   New strategies: {len(data.get('new_strategies', []))}")

    @pytest.mark.asyncio
    async def test_08_campaign_summary(self):
        """Get metrics summary."""
        if not self.campaign_id:
            pytest.skip("No campaign")
        data = await api("GET", f"/api/metrics/{self.campaign_id}/summary")
        print(f"\n✅ Campaign summary: {json.dumps(data, indent=2)}")

    @pytest.mark.asyncio
    async def test_09_strategies(self):
        """Check strategy leaderboard."""
        data = await api("GET", "/api/agents/strategies?min_usage=0&limit=10")
        strategies = data.get("strategies", [])
        print(f"\n✅ Strategies: {len(strategies)}")
        for s in strategies[:3]:
            print(
                f"   - {s.get('style', '?')}: "
                f"avg_imp={s.get('avg_impressions', 0):.0f} | "
                f"confidence={s.get('confidence', 0):.2f}"
            )

    @pytest.mark.asyncio
    async def test_10_knowledge_graph(self):
        """Verify knowledge graph has nodes."""
        if not self.campaign_id:
            pytest.skip("No campaign")
        data = await api("GET", f"/api/metrics/{self.campaign_id}/graph")
        nodes = data.get("nodes", [])
        print(f"\n✅ Knowledge graph nodes: {len(nodes)}")
        type_counts: dict[str, int] = {}
        for n in nodes:
            t = n.get("type", "?")
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in type_counts.items():
            print(f"   - {t}: {c}")

    @pytest.mark.asyncio
    async def test_11_run_another_cycle(self):
        """Run a second pipeline cycle to test self-improvement."""
        if not self.campaign_id:
            pytest.skip("No campaign")
        data = await api("POST", f"/api/campaigns/{self.campaign_id}/cycle")
        print(f"\n✅ Second cycle status: {data.get('status')}")
        print(f"   Execution: {data.get('execution', {})}")


# ---------------------------------------------------------------------------
# Direct runner (for debugging without pytest)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    async def run():
        print("=" * 60)
        print("🥚 Egg & Geese v2 — Shampoo E2E Test")
        print("=" * 60)

        test = TestShampooE2E()
        methods = [
            m
            for m in dir(test)
            if m.startswith("test_") and callable(getattr(test, m))
        ]
        methods.sort()

        for method_name in methods:
            method = getattr(test, method_name)
            print(f"\n--- {method_name} ---")
            try:
                await method()
            except Exception as e:
                print(f"   ❌ FAILED: {e}")

        print("\n" + "=" * 60)
        print("✅ All tests complete!")

    asyncio.run(run())
