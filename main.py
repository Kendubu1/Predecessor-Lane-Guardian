"""Lane Guardian - Predecessor game timer bot entry point."""
import asyncio
import logging
import os
import random
import signal
from typing import Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from commands import GameCommands
from config import ConfigManager
from health_check import HealthCheck
from services import VoiceService
from timer import GameTimer

load_dotenv()

# ---------------------------------------------------------------- logging
_handlers: list = [logging.StreamHandler()]
_log_file = os.getenv('LOG_FILE')
if _log_file:
    _handlers.append(logging.FileHandler(_log_file))
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=_handlers,
)
logger = logging.getLogger('PredTimer')


def check_voice_dependencies() -> bool:
    """Ensure everything needed for voice is present. Returns True when OK."""
    ok = True

    if not discord.voice_client.has_nacl:
        logger.error("PyNaCl is not installed. Voice will not work: pip install -r requirements.txt")
        ok = False

    # Discord requires the DAVE end-to-end encryption protocol for every voice
    # connection since 2026-03-02. Without the `davey` bindings the bot joins a
    # channel and is immediately kicked (voice websocket close 4017).
    if not getattr(discord.voice_client, 'has_dave', False):
        logger.error(
            "The 'davey' package is not installed, so DAVE end-to-end voice encryption "
            "is unavailable. Discord will disconnect the bot right after it joins a "
            "voice channel. Install it with: pip install -r requirements.txt"
        )
        ok = False

    if not discord.opus.is_loaded():
        for lib in filter(None, [os.getenv("OPUS_LIB"), "libopus.so.0", "libopus", "opus"]):
            try:
                discord.opus.load_opus(lib)
                if discord.opus.is_loaded():
                    logger.info(f"Loaded Opus library: {lib}")
                    break
            except Exception:
                continue
        if not discord.opus.is_loaded():
            logger.error("Opus library could not be loaded (install libopus0 or set OPUS_LIB).")
            ok = False

    return ok


class PredecessorBot(commands.Bot):
    """Discord client wiring together config, timers and voice."""

    def __init__(self):
        intents = discord.Intents.default()
        # Privileged: needed to enumerate members with the Administrator permission.
        # Enable "Server Members Intent" in the Discord developer portal.
        intents.members = True
        intents.voice_states = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            activity=discord.Game(name="/pred help"),
            description="Predecessor Game Timer Bot",
        )

        self.timers: Dict[int, GameTimer] = {}
        self._announce_tasks: set = set()
        self.config_manager = ConfigManager(os.getenv('CONFIG_PATH', 'server_configs.json'))
        self.voice_service = VoiceService(self)
        self.health_check: Optional[HealthCheck] = None
        logger.info("PredecessorBot initialized")

    # ------------------------------------------------------------- timers
    def get_timer(self, guild_id: int, create: bool = True) -> Optional[GameTimer]:
        timer = self.timers.get(guild_id)
        if timer is None and create:
            timer = self.timers[guild_id] = GameTimer(guild_id)
        return timer

    # ------------------------------------------------------------- lifecycle
    async def setup_hook(self) -> None:
        logger.info("Adding game commands...")
        self.tree.add_command(GameCommands(self))
        for command in self.tree.get_commands():
            if isinstance(command, app_commands.Group):
                for subcmd in command.commands:
                    logger.info(f"  /{command.name} {subcmd.name} - {subcmd.description}")

        # Azure App Service sets PORT and expects something to answer on it.
        health_port = int(os.getenv('HEALTH_PORT') or os.getenv('PORT') or '8080')
        self.health_check = HealthCheck(self, port=health_port)
        try:
            await self.health_check.start()
        except OSError as e:
            logger.warning(f"Health check server not started on port {health_port}: {e}")

        logger.info("Syncing slash commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} top-level command(s)")
        except Exception as e:
            logger.error(f"Command sync failed: {e}", exc_info=True)

        self.check_timers.start()
        self.daily_admin_sync.start()
        logger.info("Setup complete")

    async def close(self) -> None:
        logger.info("Shutting down...")
        self.check_timers.cancel()
        self.daily_admin_sync.cancel()
        for vc in list(self.voice_clients):
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass
        if self.health_check:
            await self.health_check.stop()
        self.voice_service.tts_service.cleanup()
        await super().close()

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id}) in {len(self.guilds)} guild(s)')
        for guild in self.guilds:
            await self._sync_guild_admins(guild)

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"Joined new guild: {guild.name} ({guild.id})")
        await self._sync_guild_admins(guild)

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"Removed from guild: {guild.name} ({guild.id})")
        self.timers.pop(guild.id, None)
        self.voice_service.forget_guild(guild.id)

    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState, after: discord.VoiceState):
        """Stop the timer if we get kicked from voice; leave when the channel empties."""
        guild = member.guild

        if member.id == self.user.id:
            if before.channel is not None and after.channel is None:
                logger.info(f"[{guild.id}] Voice connection ended")
                timer = self.get_timer(guild.id, create=False)
                if timer and timer.is_active:
                    timer.stop()
                self.voice_service.forget_guild(guild.id)
            return

        voice_client = guild.voice_client
        if voice_client and before.channel == voice_client.channel:
            humans = [m for m in voice_client.channel.members if not m.bot]
            if not humans:
                logger.info(f"[{guild.id}] Voice channel empty, leaving")
                timer = self.get_timer(guild.id, create=False)
                if timer and timer.is_active:
                    timer.stop()
                await self.voice_service.cleanup_voice_clients(guild)

    # ------------------------------------------------------------- admins
    async def _sync_guild_admins(self, guild: discord.Guild) -> None:
        try:
            new_admins = self.config_manager.sync_discord_admins(guild)
            if new_admins:
                logger.info(f"Synced {new_admins} Discord admin(s) for guild {guild.name} ({guild.id})")
            await self._detect_bot_inviter(guild)
        except Exception as e:
            logger.error(f"Error syncing admins for guild {guild.id}: {e}")

    async def _detect_bot_inviter(self, guild: discord.Guild) -> None:
        """Record who added the bot (from the audit log) and make them an admin."""
        try:
            config = self.config_manager.get_server_config(guild.id)
            if config.get('settings', {}).get('bot_inviter') is not None:
                return

            async for entry in guild.audit_logs(limit=50, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.target.id == self.user.id and entry.user:
                    self.config_manager.add_bot_inviter(guild.id, entry.user.id)
                    logger.info(f"Detected bot inviter {entry.user} ({entry.user.id}) for guild {guild.id}")
                    return
            logger.debug(f"Could not detect bot inviter from audit logs for guild {guild.id}")
        except discord.Forbidden:
            logger.debug(f"Missing permission to read audit logs for guild {guild.id}")
        except Exception as e:
            logger.error(f"Error detecting bot inviter for guild {guild.id}: {e}")

    # ------------------------------------------------------------- loops
    @tasks.loop(seconds=1.0)
    async def check_timers(self):
        """Fire due announcements for every guild with a running timer."""
        for voice_client in list(self.voice_clients):
            guild_id = voice_client.guild.id
            timer = self.timers.get(guild_id)
            if not timer or not timer.is_active or not voice_client.is_connected():
                continue

            try:
                current_time = timer.get_game_time()
                server_config = self.config_manager.get_server_config(guild_id)
                settings = server_config.get('settings', {})
                warning_time = int(settings.get('tts_settings', {}).get('warning_time', 0) or 0)
                events = self.config_manager.get_server_timers(guild_id, mode=timer.mode)

                # Fire in chronological order so simultaneous events queue sensibly.
                for event_name, event in sorted(events.items(), key=lambda kv: kv[1].get('time', 0)):
                    event_time = int(event.get('time', 0))
                    if event_name in timer.announced_events:
                        continue
                    if current_time > event_time + warning_time + 5:
                        # Missed it (e.g. timer started late); don't spam old events.
                        timer.announced_events.add(event_name)
                        continue
                    if current_time >= event_time - warning_time:
                        messages = event.get('messages') or [event.get('message', 'Timer event')]
                        message = random.choice(messages)
                        timer.announced_events.add(event_name)
                        task = asyncio.create_task(
                            self._announce(voice_client, message, settings, event_name)
                        )
                        self._announce_tasks.add(task)
                        task.add_done_callback(self._announce_tasks.discard)
            except Exception as e:
                logger.error(f"[{guild_id}] Error in check_timers: {e}", exc_info=True)

    async def _announce(self, voice_client: discord.VoiceClient, message: str,
                        settings: dict, event_name: str) -> None:
        try:
            await self.voice_service.play_announcement(voice_client, message, settings)
        except Exception as e:
            logger.error(f"[{voice_client.guild.id}] Failed to announce {event_name}: {e}")

    @check_timers.before_loop
    async def before_check_timers(self):
        await self.wait_until_ready()

    @tasks.loop(hours=24.0)
    async def daily_admin_sync(self):
        logger.info("Starting daily admin sync for all guilds...")
        for guild in self.guilds:
            await self._sync_guild_admins(guild)

    @daily_admin_sync.before_loop
    async def before_daily_admin_sync(self):
        await self.wait_until_ready()


async def _run(token: str) -> None:
    bot = PredecessorBot()
    loop = asyncio.get_running_loop()

    def _request_shutdown(*_):
        logger.info("Termination signal received")
        loop.create_task(bot.close())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except (NotImplementedError, RuntimeError):
            pass  # Windows

    async with bot:
        await bot.start(token)


def run_bot() -> None:
    """Validate the environment and start the bot."""
    if not check_voice_dependencies():
        logger.critical("Missing required voice dependencies. Exiting.")
        raise SystemExit(1)

    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.critical("DISCORD_TOKEN is not set (put it in .env or the container environment).")
        raise SystemExit(1)

    try:
        asyncio.run(_run(token))
    except discord.LoginFailure:
        logger.critical("Discord rejected the token. Check DISCORD_TOKEN.")
        raise SystemExit(1)
    except discord.PrivilegedIntentsRequired:
        logger.critical(
            "Enable 'Server Members Intent' for this bot at "
            "https://discord.com/developers/applications -> Bot -> Privileged Gateway Intents."
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_bot()
