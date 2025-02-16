from aiohttp import web
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger('PredTimer.HealthCheck')

class HealthCheck:
    def __init__(self, bot, port=8000):
        self.bot = bot
        self.port = port
        self.start_time = datetime.now()
        self.app = web.Application()
        self.app.router.add_get('/', self.handle_health_check)
        self.app.router.add_get('/health', self.handle_health_check)
        
    async def handle_health_check(self, request):
        """Handle health check requests."""
        try:
            uptime = datetime.now() - self.start_time
            status = {
                'status': 'healthy',
                'uptime': str(uptime),
                'bot_connected': self.bot.is_ready(),
                'voice_connections': len(self.bot.voice_clients),
                'active_timers': self.bot.timer.is_active
            }
            return web.json_response(status)
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return web.json_response(
                {'status': 'unhealthy', 'error': str(e)}, 
                status=500
            )

    async def start(self):
        """Start the health check server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health check server running on port {self.port}")
