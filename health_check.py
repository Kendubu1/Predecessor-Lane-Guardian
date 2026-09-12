"""Tiny HTTP health endpoint used by Docker HEALTHCHECK and uptime monitors."""
import logging
from datetime import datetime, timezone

from aiohttp import web

logger = logging.getLogger('PredTimer.HealthCheck')


class HealthCheck:
    def __init__(self, bot, port: int = 8080):
        self.bot = bot
        self.port = port
        self.start_time = datetime.now(timezone.utc)
        self.app = web.Application()
        self.app.router.add_get('/', self.handle_liveness)
        self.app.router.add_get('/health', self.handle_health_check)
        self._runner: web.AppRunner | None = None

    async def handle_liveness(self, request: web.Request) -> web.Response:
        """Always 200: the process is up. Used by platform pings (e.g. Azure)."""
        return web.json_response({'status': 'alive', 'bot_connected': self.bot.is_ready()})

    async def handle_health_check(self, request: web.Request) -> web.Response:
        """Return 200 when the bot is connected to Discord, 503 otherwise."""
        try:
            ready = self.bot.is_ready()
            uptime = datetime.now(timezone.utc) - self.start_time
            active_timers = [
                str(guild_id) for guild_id, timer in getattr(self.bot, 'timers', {}).items()
                if timer.is_active
            ]
            status = {
                'status': 'healthy' if ready else 'starting',
                'uptime_seconds': int(uptime.total_seconds()),
                'bot_connected': ready,
                'guilds': len(self.bot.guilds) if ready else 0,
                'voice_connections': len(self.bot.voice_clients),
                'active_timers': len(active_timers),
                'active_timer_guilds': active_timers,
                'latency_ms': round(self.bot.latency * 1000) if ready else None,
            }
            return web.json_response(status, status=200 if ready else 503)
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return web.json_response({'status': 'unhealthy', 'error': str(e)}, status=500)

    async def start(self) -> None:
        """Start the health check server."""
        self._runner = web.AppRunner(self.app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health check server running on port {self.port}")

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
