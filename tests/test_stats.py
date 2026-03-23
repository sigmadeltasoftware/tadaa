import json
import pytest
from aiohttp import web
from tadaa.relay.stats import create_stats_app
from tadaa.relay.daemon import RelayStats


@pytest.fixture
def relay_stats():
    stats = RelayStats()
    stats.packets_relayed = 42
    stats.packets_dropped = 3
    stats.last_rssi = -68.5
    stats.known_devices = {"0001", "0002"}
    return stats


@pytest.mark.asyncio
async def test_stats_endpoint(aiohttp_client, relay_stats):
    app = create_stats_app(relay_stats)
    client = await aiohttp_client(app)
    resp = await client.get("/stats")
    assert resp.status == 200
    data = await resp.json()
    assert data["packets_relayed"] == 42
    assert data["packets_dropped"] == 3
    assert "uptime" in data
    assert "0001" in data["known_devices"]


@pytest.mark.asyncio
async def test_health_endpoint(aiohttp_client, relay_stats):
    app = create_stats_app(relay_stats)
    client = await aiohttp_client(app)
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
