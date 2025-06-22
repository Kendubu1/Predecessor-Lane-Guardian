# Standard library imports
import os
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Set

# Discord imports
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Local imports
from health_check import HealthCheck

def check_voice_dependencies() -> bool:
    """Ensure required voice dependencies are available."""
    missing = False
    if not discord.voice_client.has_nacl:
        logger.error(
            "PyNaCl library is not installed. Voice features will not work. "
            "Install with 'pip install -r requirements.txt' or 'pip install discord.py[voice]'."
        )
        missing = True

    if not discord.opus.is_loaded():
        # Try a few common library names to support different platforms
        opus_libs = [
            os.getenv("OPUS_LIB"),  # allow override via environment variable
            "libopus.so.0",
            "libopus",
            "opus",
        ]
        for lib in filter(None, opus_libs):
            try:
                discord.opus.load_opus(lib)
                if discord.opus.is_loaded():
                    break
            except Exception:
                continue

        if not discord.opus.is_loaded():
            logger.error(
                "Opus library could not be loaded. Voice playback may fail."
            )
            missing = True

    return not missing
from config import ConfigManager
from services import TTSService, VoiceService
from commands import GameCommands


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PredTimer')

class GameTimer:
    """Handles game time tracking and event management."""
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.is_active: bool = False
        self.mode: str = 'standard'
        self.announced_events: Set[str] = set()
        logger.info("GameTimer initialized")

    def start(self, time_str: str, mode: str = 'standard') -> None:
        """Start the timer from a specific time point."""
        try:
            minutes, seconds = map(int, time_str.split(':'))
            current_time = datetime.now()
            self.start_time = current_time - timedelta(minutes=minutes, seconds=seconds)
            self.is_active = True
            self.mode = mode
            self.announced_events.clear()
            logger.info(f"Timer started at {time_str} in {mode} mode")
        except ValueError as e:
            logger.error(f"Error parsing time string: {e}")
            raise

    def get_game_time(self) -> int:
        """Get current game time in seconds."""
        if not self.is_active or not self.start_time:
            return 0
        elapsed = datetime.now() - self.start_time
        return int(elapsed.total_seconds())

    def stop(self) -> None:
        """Stop the timer and clear announced events."""
        self.is_active = False
        self.announced_events.clear()
        logger.info("Timer stopped")

class PredecessorBot(commands.Bot):
    """Main bot class handling Discord integration and game timing."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix='!', 
            intents=intents,
            activity=discord.Game(name="/pred help"),
            description="Predecessor Game Timer Bot"
        )
        
        # Initialize core components
        self.timer = GameTimer()
        self.config_manager = ConfigManager()
        self.tts_service = TTSService()
        self.voice_service = VoiceService(self)
        
        logger.info("PredecessorBot initialized")

    async def setup_hook(self) -> None:
            """Set up the bot's initial state and start background tasks."""
            try:
                # Add game commands
                logger.info("Adding game commands...")
                game_commands = GameCommands(self)
                self.tree.add_command(game_commands)
                
                # Log all commands in the tree
                logger.info("Available commands in tree:")
                for command in self.tree.get_commands():
                    logger.info(f"/{command.name}")
                    # If it's a group, log its subcommands
                    if isinstance(command, app_commands.Group):
                        for subcmd in command.commands:
                            logger.info(f"  /{command.name} {subcmd.name} - {subcmd.description}")
                
                # Start health check server
                logger.info("Starting health check server...")
                self.health_check = HealthCheck(self, port=8081)
                await self.health_check.start()
        
                # Sync command tree
                logger.info("Syncing commands...")
                await self.tree.sync()
                logger.info("Command sync complete")
                
                # Start background tasks
                logger.info("Starting background tasks...")
                self.check_timers.start('standard')
                
                logger.info("Setup complete!")
                
            except Exception as e:
                logger.error(f"Error in setup_hook: {e}", exc_info=True)
                raise

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        # Add an additional sync attempt here for redundancy
        try:
            await self.tree.sync()
            logger.info("Commands synced in on_ready")
        except Exception as e:
            logger.error(f"Error syncing commands in on_ready: {e}")
        logger.info('------')

        # Ensure each guild owner and configured secondary owners
        # are recorded as admin users
        for guild in self.guilds:
            config = self.config_manager.get_server_config(guild.id)
            admin_users = config.get('settings', {}).get('admin_users', [])
            secondary = config.get('settings', {}).get('secondary_owners', [])
            updated = False

            for owner_id in [guild.owner_id, *secondary]:
                if owner_id not in admin_users:
                    admin_users.append(owner_id)
                    updated = True

            if updated:
                self.config_manager.update_server_setting(
                    guild.id,
                    'settings.admin_users',
                    admin_users,
                )
                logger.info(
                    f"Added owner IDs {secondary + [guild.owner_id]} as admins for {guild.id}"
                )

    async def on_guild_join(self, guild: discord.Guild):
        """Automatically add the guild owner to admin list when joining."""
        config = self.config_manager.get_server_config(guild.id)
        admin_users = config.get('settings', {}).get('admin_users', [])
        secondary = config.get('settings', {}).get('secondary_owners', [])
        updated = False

        for owner_id in [guild.owner_id, *secondary]:
            if owner_id not in admin_users:
                admin_users.append(owner_id)
                updated = True

        if updated:
            self.config_manager.update_server_setting(
                guild.id,
                'settings.admin_users',
                admin_users,
            )
            logger.info(
                f"Guild join: added owners {secondary + [guild.owner_id]} as admins for {guild.id}"
            )
        
    # In main.py, update the check_timers method
    @tasks.loop(seconds=1.0)
    async def check_timers(self, mode: str = 'standard'):
        """Check and announce timer events for the given mode."""
        if not self.timer.is_active:
            return

        try:
            current_time = self.timer.get_game_time()
            
            for voice_client in self.voice_clients:
                server_config = self.config_manager.get_server_config(voice_client.guild.id)
                active_mode = self.timer.mode if hasattr(self.timer, 'mode') else mode
                timers = self.config_manager.get_server_timers(voice_client.guild.id, mode=active_mode)
                settings = server_config.get('settings', {})
                
                warning_time = settings.get('tts_settings', {}).get('warning_time', 30)
                
                for event_name, timer_config in timers.items():
                    event_id = f"{voice_client.guild.id}_{event_name}"
                    
                    # Skip if event already announced or too late
                    if (event_id in self.timer.announced_events or 
                        current_time > timer_config['time'] + warning_time):
                        continue
                    
                    # Check if it's time to announce
                    if current_time >= timer_config['time'] - warning_time:
                        # Get messages list and select one randomly
                        messages = timer_config.get('messages', [])
                        if not messages:  # If messages list is empty, try legacy 'message' field
                            messages = [timer_config.get('message', 'Timer event')]
                        
                        message = random.choice(messages)
                        
                        await self.voice_service.play_announcement(
                            voice_client,
                            message,
                            settings
                        )
                        self.timer.announced_events.add(event_id)
                        
        except Exception as e:
            logger.error(f"Error in check_timers: {e}", exc_info=True)

def run_bot():
    """Start the bot."""
    # Load environment variables
    load_dotenv()

    if not check_voice_dependencies():
        logger.critical("Missing required voice dependencies. Exiting.")
        return
    
    # Get Discord token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("No Discord token found in environment variables!")
        return
        
    try:
        # Create and run bot
        bot = PredecessorBot()
        bot.run(token, log_handler=None)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")

if __name__ == "__main__":
    run_bot()
