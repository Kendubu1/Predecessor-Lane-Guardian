import os
import logging
import random
from health_check import HealthCheck
from datetime import datetime, timedelta
from typing import Optional, Set
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

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
        self.announced_events: Set[str] = set()
        logger.info("GameTimer initialized")

    def start(self, time_str: str) -> None:
        """Start the timer from a specific time point."""
        try:
            minutes, seconds = map(int, time_str.split(':'))
            current_time = datetime.now()
            self.start_time = current_time - timedelta(minutes=minutes, seconds=seconds)
            self.is_active = True
            self.announced_events.clear()
            logger.info(f"Timer started at {time_str}")
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
        self.voice_service = VoiceService()
        
        logger.info("PredecessorBot initialized")

    async def setup_hook(self) -> None:
        """Set up the bot's initial state and start background tasks."""
        try:
            # Add game commands
            logger.info("Adding game commands group...")
            game_commands = GameCommands(self)
            self.tree.add_command(game_commands)
            
            # Start health check server
            logger.info("Starting health check server...")
            self.health_check = HealthCheck(self, port=8081)
            await self.health_check.start()
    
            # Sync command tree with verbose logging
            logger.info("Starting command sync...")
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} commands")
                for command in synced:
                    logger.info(f"Synced command: {command.name}")
            except Exception as e:
                logger.error(f"Error syncing commands: {e}")
                raise
            
            # Start background tasks
            logger.info("Starting background tasks...")
            self.check_timers.start()
            
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

    # In main.py, update the check_timers method
    @tasks.loop(seconds=1.0)
    async def check_timers(self):
        """Check and announce timer events."""
        if not self.timer.is_active:
            return

        try:
            current_time = self.timer.get_game_time()
            
            for voice_client in self.voice_clients:
                server_config = self.config_manager.get_server_config(voice_client.guild.id)
                timers = server_config.get('timers', {})
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
