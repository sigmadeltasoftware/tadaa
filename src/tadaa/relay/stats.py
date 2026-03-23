"""HTTP stats endpoint for the relay daemon."""

from aiohttp import web
from tadaa.relay.daemon import RelayStats


async def handle_stats(request: web.Request) -> web.Response:
    stats: RelayStats = request.app["relay_stats"]
    return web.json_response(stats.to_dict())


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_stats_app(stats: RelayStats) -> web.Application:
    app = web.Application()
    app["relay_stats"] = stats
    app.router.add_get("/stats", handle_stats)
    app.router.add_get("/health", handle_health)
    return app
