# Standard library imports
import os
import json
import asyncio
import logging
import tempfile
import base64
from datetime import datetime, timedelta
from typing import Optional, List, Set

# Discord imports
import discord
from discord import app_commands

# Local imports
from health_check import HealthCheck
from config import (
    ConfigManager,
    TimerCategory,
    TTSLanguage,
    TTSAccent,
    TTSSpeed,
    VALID_LANG_ACCENT_PAIRS
)
from services import TTSService, VoiceService


logger = logging.getLogger('PredTimer.Commands')

class GameCommands(app_commands.Group):
    """Handles all game-related commands for the bot."""
    
    def __init__(self, bot):
        super().__init__(name="pred", description="pred game timer commands")
        self.bot = bot
        
        # Log all registered commands
        logger.info("Registering bot commands:")
        # Get all methods that are commands
        for name, method in self.__class__.__dict__.items():
            if isinstance(method, app_commands.Command):
                logger.info(f"  /pred {method.name} - {method.description}")
        
        logger.info("GameCommands initialization complete")

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use admin commands."""
        if interaction.user.id == interaction.guild.owner_id:
            return True
            
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        admin_roles = config.get('settings', {}).get('admin_roles', [])
        return any(role.id in admin_roles for role in interaction.user.roles)

    def validate_config(self, config_data: dict) -> tuple[bool, str, dict]:
        """
        Validate configuration data and sanitize it.
        Returns (is_valid, error_message, sanitized_config)
        """
        try:
            # Basic structure validation
            required_keys = {'settings', 'timers'}
            if not isinstance(config_data, dict):
                return False, "Configuration must be a dictionary", {}
            
            if not all(key in config_data for key in required_keys):
                return False, f"Configuration missing required sections: {required_keys}", {}

            # Initialize sanitized config with default structure
            sanitized = {
                'settings': {
                    'volume': 1.0,
                    'admin_roles': [],
                    'admin_users': [],
                    'tts_settings': {
                        'language': 'en',
                        'accent': 'co.in',
                        'warning_time': 30,
                        'speed': 1.0,
                        'pitch': 1.0,
                        'word_gap': 0.1,
                        'emphasis_volume': 1.2,
                        'use_phonetics': False,
                        'capitalize_proper_nouns': True,
                        'number_to_words': True,
                        'custom_pronunciations': {}
                    }
                },
                'timers': {}
            }

            # Validate settings section
            settings = config_data.get('settings', {})
            if not isinstance(settings, dict):
                return False, "Settings section must be a dictionary", {}

            # Volume validation
            try:
                volume = float(settings.get('volume', 1.0))
                sanitized['settings']['volume'] = max(0.0, min(1.0, volume))
            except (ValueError, TypeError):
                sanitized['settings']['volume'] = 1.0

            # Admin roles validation
            admin_roles = settings.get('admin_roles', [])
            if isinstance(admin_roles, list):
                sanitized['settings']['admin_roles'] = [
                    int(role_id) for role_id in admin_roles 
                    if str(role_id).isdigit()
                ]
                
            # Admin users validation
            admin_users = settings.get('admin_users', [])
            if isinstance(admin_users, list):
                sanitized['settings']['admin_users'] = [
                    int(user_id) for user_id in admin_users 
                    if str(user_id).isdigit()
                ]

            # TTS settings validation
            tts_settings = settings.get('tts_settings', {})
            if not isinstance(tts_settings, dict):
                tts_settings = {}

            # Language and accent validation
            language = str(tts_settings.get('language', 'en'))
            accent = str(tts_settings.get('accent', 'co.in'))
            
            # Check if language-accent pair is valid
            if (language, accent) in VALID_LANG_ACCENT_PAIRS:
                sanitized['settings']['tts_settings']['language'] = language
                sanitized['settings']['tts_settings']['accent'] = accent
            
            # Other TTS settings validation
            try:
                warning_time = int(tts_settings.get('warning_time', 30))
                sanitized['settings']['tts_settings']['warning_time'] = max(0, min(60, warning_time))
            except (ValueError, TypeError):
                sanitized['settings']['tts_settings']['warning_time'] = 30

            try:
                speed = float(tts_settings.get('speed', 1.0))
                sanitized['settings']['tts_settings']['speed'] = max(0.5, min(2.0, speed))
            except (ValueError, TypeError):
                sanitized['settings']['tts_settings']['speed'] = 1.0

            # Timers validation
            timers = config_data.get('timers', {})
            if not isinstance(timers, dict):
                return False, "Timers section must be a dictionary", {}

            for name, timer in timers.items():
                if not isinstance(timer, dict):
                    continue

                # Check for either messages array or single message
                messages = timer.get('messages', [timer.get('message', 'Timer event')])
                if isinstance(messages, str):
                    messages = [messages]
                elif not isinstance(messages, list):
                    continue

                try:
                    time_value = int(timer['time'])
                    if not 0 <= time_value <= 3600:  # Max 1 hour
                        continue
                        
                    # Validate message length and content
                    valid_messages = []
                    for msg in messages:
                        msg = str(msg).strip()
                        if msg and len(msg) <= 200:  # Message length limit
                            valid_messages.append(msg)
                    
                    if not valid_messages:
                        valid_messages = ['Timer event']

                    category = str(timer.get('category', TimerCategory.REMINDER.value))
                    if category not in [cat.value for cat in TimerCategory]:
                        category = TimerCategory.REMINDER.value

                    sanitized['timers'][str(name)] = {
                        'time': time_value,
                        'messages': valid_messages,
                        'category': category
                    }
                except (ValueError, TypeError, KeyError):
                    continue

            if not sanitized['timers']:
                return False, "No valid timers found in configuration", {}

            return True, "", sanitized

        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False, f"Error validating configuration: {str(e)}", {}


    @app_commands.command(name="add_admin")
    async def add_admin(self, interaction: discord.Interaction, user: discord.User):
        """Add a user as a bot admin."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message(
                "You don't have permission to modify admin users!",
                ephemeral=True
            )
            return

        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        admin_users = config['settings'].get('admin_users', [])
        
        if user.id in admin_users:
            await interaction.response.send_message(
                f"{user.name} is already an admin!",
                ephemeral=True
            )
            return

        admin_users.append(user.id)
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.admin_users',
            admin_users
        )
        
        await interaction.response.send_message(
            f"Added {user.name} as a bot admin.",
            ephemeral=True
        )

    @app_commands.command(name="set_tts")
    @app_commands.describe(
        speed="Voice speed (0.5 = half speed, 1.0 = normal, up to 2.0 = double speed)",
        language="Voice language",
        accent="Voice accent",
        warning_time="Warning time in seconds"
    )
    async def set_tts(self, interaction: discord.Interaction, 
                    language: Optional[str] = None,
                    accent: Optional[str] = None,
                    warning_time: Optional[int] = None,
                    speed: Optional[float] = None):
        """Configure TTS settings."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify settings!")
            return
        
        # Get current settings first
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        current_settings = config['settings'].get('tts_settings', {})
        
        # Prepare new settings, starting with current settings
        settings = current_settings.copy()
        error_message = None
        
        # Validate speed and update
        if speed is not None:
            if 0.5 <= speed <= 2.0:
                settings['speed'] = speed
            else:
                await interaction.response.send_message(
                    "Speed must be between 0.5 (half speed) and 2.0 (double speed)",
                    ephemeral=True
                )
                return
        
        # Validate language and accent combination
        if language and accent:
            if (language, accent) not in VALID_LANG_ACCENT_PAIRS:
                error_message = f"Invalid language ({language}) and accent ({accent}) combination"
            else:
                settings['language'] = language
                settings['accent'] = accent
        elif language:
            settings['language'] = language
        elif accent:
            settings['accent'] = accent
            
        if error_message:
            await interaction.response.send_message(error_message, ephemeral=True)
            return
            
        if warning_time is not None:
            settings['warning_time'] = max(0, min(60, warning_time))
        
        # Update the settings
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.tts_settings',
            settings
        )
        
        # Create response embed
        embed = discord.Embed(
            title="TTS Settings Updated",
            color=discord.Color.green()
        )
        
        # Get the display name for the language-accent combination
        lang_accent_name = VALID_LANG_ACCENT_PAIRS.get(
            (settings.get('language'), settings.get('accent')),
            f"{settings.get('language', 'en')} ({settings.get('accent', 'co.in')})"
        )
        
        embed.add_field(
            name="Voice Settings",
            value=f"Language/Accent: {lang_accent_name}",
            inline=False
        )
        embed.add_field(
            name="Speed", 
            value=f"{settings.get('speed', 1.0)}x", 
            inline=True
        )
        if warning_time is not None:
            embed.add_field(
                name="Warning Time", 
                value=f"{settings.get('warning_time', 30)}s", 
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)

    @set_tts.autocomplete('speed')
    async def speed_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for TTS speed."""
        # Define preset speeds with descriptions
        preset_speeds = [
            (0.5, "Very Slow (0.5x)"),
            (0.75, "Slow (0.75x)"),
            (1.0, "Normal (1.0x)"),
            (1.25, "Fast (1.25x)"),
            (1.5, "Very Fast (1.5x)"),
            (1.75, "Faster (1.75x)"),
            (2.0, "Maximum (2.0x)")
        ]
        
        # If user has typed something, try to parse it
        if current:
            try:
                value = float(current)
                # If it's a valid number, add it to choices if in valid range
                if 0.5 <= value <= 2.0:
                    preset_speeds.append((value, f"Custom ({value}x)"))
            except ValueError:
                pass

        # Convert current to string for filtering
        current_str = str(current).lower()
        
        # Filter based on current input (match against both speed value and description)
        filtered = [
            (value, name) for value, name in preset_speeds
            if current_str in str(value) or current_str in name.lower()
        ]
        
        # Return formatted choices
        return [
            app_commands.Choice(name=name, value=float(value))
            for value, name in filtered[:25]  # Discord limits to 25 choices
        ]

    @set_tts.autocomplete('language')
    async def language_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for TTS languages."""
        # Get unique languages from valid combinations
        languages = set(lang for lang, _ in VALID_LANG_ACCENT_PAIRS.keys())
        
        # Filter based on current input
        filtered = [
            lang for lang in languages
            if current.lower() in lang.lower()
        ]
        filtered.sort()
        
        return [
            app_commands.Choice(name=lang, value=lang)
            for lang in filtered[:25]
        ]

    @set_tts.autocomplete('accent')
    async def accent_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for TTS accents based on selected language."""
        current_lang = interaction.namespace.language
        
        # Get valid accents for the current language
        if current_lang:
            accents = [
                (accent, name) 
                for (lang, accent), name in VALID_LANG_ACCENT_PAIRS.items()
                if lang == current_lang
            ]
        else:
            # If no language selected, show all accents
            accents = [
                (accent, name)
                for (_, accent), name in VALID_LANG_ACCENT_PAIRS.items()
            ]
        
        # Filter based on current input
        filtered = [
            (accent, name) for accent, name in accents
            if current.lower() in name.lower()
        ]
        filtered.sort(key=lambda x: x[1])  # Sort by display name
        
        return [
            app_commands.Choice(name=name, value=accent)
            for accent, name in filtered[:25]
        ]

    @app_commands.command(name="start")
    @app_commands.describe(time="Game time in M:SS format (defaults to 0:00)")
    async def start(self, interaction: discord.Interaction, time: str = "00:00"):
        """Start the game timer."""
        try:
            if not interaction.user.voice:
                await interaction.response.send_message("You need to be in a voice channel!")
                return

            voice_channel = interaction.user.voice.channel
            await self.bot.voice_service.ensure_voice_client(voice_channel, force_new=True)
            
            self.bot.timer.start(time)
            await interaction.response.send_message(f"Game timer started at {time}")
            
        except ValueError:
            await interaction.response.send_message("Invalid time format. Use M:SS (e.g., 0:05)")
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await interaction.response.send_message(f"Error: {str(e)}")

    @app_commands.command(name="stop")
    async def stop(self, interaction: discord.Interaction):
        """Stop the game timer."""
        self.bot.timer.stop()
        
        for voice_client in self.bot.voice_clients:
            if voice_client.guild == interaction.guild:
                await self.bot.voice_service.cleanup_voice_clients(interaction.guild)
            
        await interaction.response.send_message("Game timer stopped")

    @app_commands.command(name="add_timer")
    @app_commands.choices(category=[
        app_commands.Choice(name=cat.name.title(), value=cat.value)
        for cat in TimerCategory
    ])
    async def add_timer(self, interaction: discord.Interaction, 
                       name: str, time: str, message: str, 
                       category: str = TimerCategory.REMINDER.value):
        """Add a new timer event."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to add timers!")
            return

        try:
            # Convert time string to seconds
            minutes, seconds = map(int, time.split(':'))
            total_seconds = minutes * 60 + seconds

            # Get existing timer if it exists
            config = self.bot.config_manager.get_server_config(interaction.guild.id)
            existing_timer = config.get('timers', {}).get(name, {})
            
            # Get existing messages or create new list
            messages = existing_timer.get('messages', [])
            if message not in messages:
                messages.append(message)

            self.bot.config_manager.update_timer(
                interaction.guild.id,
                name,
                total_seconds,
                messages,
                category
            )

            # Create response message
            msg_count = len(messages)
            await interaction.response.send_message(
                f"Timer '{name}' updated at {time} with {msg_count} message{'s' if msg_count > 1 else ''}"
            )
            
        except ValueError:
            await interaction.response.send_message("Invalid time format. Use M:SS (e.g., 5:30)")
        except Exception as e:
            logger.error(f"Error adding timer: {e}")
            await interaction.response.send_message(f"Error adding timer: {str(e)}")

    @app_commands.command(name="remove_timer")
    async def remove_timer(self, interaction: discord.Interaction, name: str):
        """Remove a timer event."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to remove timers!")
            return

        if self.bot.config_manager.remove_timer(interaction.guild.id, name):
            await interaction.response.send_message(f"Timer '{name}' removed")
        else:
            await interaction.response.send_message(f"Timer '{name}' not found")

    @app_commands.command(name="remove_timer_message")
    async def remove_timer_message(self, interaction: discord.Interaction, 
                             timer_name: str, message_index: int):
        """Remove a specific message from a timer."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify timers!")
            return

        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        timer = config.get('timers', {}).get(timer_name)
        
        if not timer:
            await interaction.response.send_message(f"Timer '{timer_name}' not found")
            return
            
        messages = timer.get('messages', [])
        if not 0 <= message_index < len(messages):
            await interaction.response.send_message(
                f"Invalid message index. Timer has {len(messages)} message(s)"
            )
            return
            
        removed_message = messages.pop(message_index)
        
        if not messages:  # Don't allow empty message list
            messages = ["Timer event"]
            
        self.bot.config_manager.update_timer(
            interaction.guild.id,
            timer_name,
            timer['time'],
            messages,
            timer['category']
        )
        
        await interaction.response.send_message(
            f"Removed message from timer '{timer_name}': {removed_message}"
        )

    @app_commands.command(name="list_timers")
    async def list_timers(self, interaction: discord.Interaction, category: Optional[str] = None):
        """List all configured timers, optionally filtered by category."""
        timers = self.bot.config_manager.get_server_timers(interaction.guild.id, category)
        
        if not timers:
            await interaction.response.send_message(
                "No timers found" + (f" for category: {category}" if category else ""),
                ephemeral=True
            )
            return

        # Sort timers by time
        sorted_timers = sorted(timers.items(), key=lambda x: x[1]['time'])
        
        # Split timers into chunks of 25 for multiple embeds
        chunk_size = 25
        timer_chunks = [sorted_timers[i:i + chunk_size] for i in range(0, len(sorted_timers), chunk_size)]
        
        embeds = []
        for i, chunk in enumerate(timer_chunks):
            embed = discord.Embed(
                title=f"Configured Timers (Page {i+1}/{len(timer_chunks)})",
                color=discord.Color.blue()
            )

            if category:
                embed.description = f"Filtered by category: {category}"

            # Add timer fields for this chunk
            for name, timer in chunk:
                minutes = timer['time'] // 60
                seconds = timer['time'] % 60
                messages = timer.get('messages', ['No message'])
                
                # Format message list
                message_text = '\n'.join(f"{idx}. {msg}" 
                                     for idx, msg in enumerate(messages))
                
                embed.add_field(
                    name=f"{minutes:02d}:{seconds:02d} - {name}",
                    value=f"Category: {timer.get('category', 'uncategorized')}\n{message_text}",
                    inline=False
                )
            
            embeds.append(embed)

        # Send the first embed
        await interaction.response.send_message(embed=embeds[0])
        
        # Send additional embeds if they exist
        if len(embeds) > 1:
            try:
                for embed in embeds[1:]:
                    await interaction.followup.send(embed=embed)
            except Exception as e:
                logger.error(f"Error sending additional timer pages: {e}")
                await interaction.followup.send(
                    "Error displaying all timers. Some pages may be missing.",
                    ephemeral=True
                )

    @app_commands.command(name="export_config")
    async def export_config(self, interaction: discord.Interaction):
        """Export the current server configuration."""
        try:
            config = self.bot.config_manager.get_server_config(interaction.guild.id)
            
            # Convert config to a formatted JSON string
            config_str = json.dumps(config, indent=2)
            
            # Create an embed with the export details
            embed = discord.Embed(
                title="Server Configuration Export",
                description="Configuration file is attached below.",
                color=discord.Color.blue()
            )
            
            # Add settings summary
            timer_count = len(config.get('timers', {}))
            tts_settings = config['settings']['tts_settings']
            
            embed.add_field(
                name="Configuration Summary",
                value=f"• {timer_count} timers configured\n"
                      f"• Language: {tts_settings.get('language', 'en')}\n"
                      f"• Accent: {tts_settings.get('accent', 'co.in')}\n"
                      f"• Speed: {tts_settings.get('speed', 1.0)}x\n"
                      f"• Volume: {config['settings'].get('volume', 1.0)}",
                inline=False
            )

            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
                temp_file.write(config_str)
                temp_file.flush()
                
                # Send the embed with the file
                await interaction.response.send_message(
                    embed=embed,
                    file=discord.File(temp_file.name, filename=f"config_{interaction.guild.name}.json"),
                    ephemeral=True
                )

            # Clean up
            os.unlink(temp_file.name)
            
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            await interaction.response.send_message(
                "Error exporting configuration. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="import_config")
    @app_commands.describe(
        file="The configuration file to import (JSON)",
        merge="Whether to merge with existing configuration or replace entirely",
        keep_existing_timers="Keep existing timers when importing (only with merge=True)"
    )
    async def import_config(self, 
                          interaction: discord.Interaction, 
                          file: discord.Attachment,
                          merge: bool = True,
                          keep_existing_timers: bool = True):
        """Import a server configuration from a JSON file."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message(
                "You need admin permissions to import configurations!",
                ephemeral=True
            )
            return

        try:
            # Check file size and type
            if file.size > 1024 * 1024:  # 1MB limit
                await interaction.response.send_message(
                    "File too large. Configuration files should be under 1MB.",
                    ephemeral=True
                )
                return

            if not file.filename.endswith('.json'):
                await interaction.response.send_message(
                    "Please provide a .json file containing the configuration.",
                    ephemeral=True
                )
                return

            # Read and parse the file
            config_bytes = await file.read()
            config_str = config_bytes.decode('utf-8')
            
            try:
                config_data = json.loads(config_str)
            except json.JSONDecodeError:
                await interaction.response.send_message(
                    "Invalid JSON format. Please ensure the file contains valid JSON.",
                    ephemeral=True
                )
                return
            
            # Validate and sanitize the configuration
            is_valid, error_message, sanitized_config = self.validate_config(config_data)
            
            if not is_valid:
                await interaction.response.send_message(
                    f"Invalid configuration: {error_message}",
                    ephemeral=True
                )
                return
            
            # Get current config if merging
            if merge:
                current_config = self.bot.config_manager.get_server_config(interaction.guild.id)
                
                if keep_existing_timers:
                    # Merge timers, keeping existing ones
                    sanitized_config['timers'] = {
                        **current_config.get('timers', {}),
                        **sanitized_config.get('timers', {})
                    }
                
                # Merge settings
                current_config['settings'].update(sanitized_config['settings'])
                sanitized_config = current_config
            
            # Update the server configuration
            self.bot.config_manager.configs[str(interaction.guild.id)] = sanitized_config
            self.bot.config_manager.save_configs()
            
            # Create summary embed
            embed = discord.Embed(
                title="Configuration Imported Successfully",
                color=discord.Color.green()
            )
            
            timer_count = len(sanitized_config.get('timers', {}))
            tts_settings = sanitized_config['settings']['tts_settings']
            
            # Get the display name for the language-accent combination
            lang_accent_name = VALID_LANG_ACCENT_PAIRS.get(
                (tts_settings['language'], tts_settings['accent']),
                f"{tts_settings['language']} ({tts_settings['accent']})"
            )
            
            embed.add_field(
                name="Imported Configuration",
                value=f"• {timer_count} total timers\n"
                      f"• Voice: {lang_accent_name}\n"
                      f"• Speed: {tts_settings['speed']}x\n"
                      f"• Warning Time: {tts_settings.get('warning_time', 30)}s\n"
                      f"• Volume: {sanitized_config['settings']['volume']:.1f}",
                inline=False
            )
            
            if merge:
                embed.add_field(
                    name="Merge Details",
                    value="✓ Merged with existing configuration\n" +
                          ("✓ Kept existing timers\n" if keep_existing_timers else "✗ Replaced existing timers\n"),
                    inline=False
                )
            
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error importing config: {e}")
            await interaction.response.send_message(
                "Error importing configuration. Please check the file and try again.",
                ephemeral=True
            )

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction):
        """Simple test command to verify the bot is working."""
        await interaction.response.send_message("Pong! Bot is working", ephemeral=True)

    # Add this after your other commands in the GameCommands class

    @app_commands.command(name="say")
    @app_commands.describe(
        message="Message to speak through TTS",
        ephemeral="Whether to show the command response only to you"
    )
    async def say(self, 
                interaction: discord.Interaction, 
                message: str,
                ephemeral: bool = True):
        """Say a message through TTS."""
        try:
            if not interaction.user.voice:
                await interaction.response.send_message(
                    "You need to be in a voice channel!", 
                    ephemeral=True
                )
                return

            voice_channel = interaction.user.voice.channel
            voice_client = await self.bot.voice_service.ensure_voice_client(voice_channel)
            
            # Get server settings and play message
            config = self.bot.config_manager.get_server_config(interaction.guild.id)
            
            # Send response before playing
            await interaction.response.send_message(
                f"Playing: {message}", 
                ephemeral=ephemeral
            )
            
            await self.bot.voice_service.play_announcement(
                voice_client,
                message,
                config['settings']
            )
            
        except Exception as e:
            logger.error(f"Error in say command: {e}")
            await interaction.response.send_message(
                f"Error playing message: {str(e)}", 
                ephemeral=True
            )

    @list_timers.autocomplete('category')
    async def category_autocomplete(self, 
                                  interaction: discord.Interaction, 
                                  current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for timer categories."""
        categories = set()
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        
        # Collect all unique categories
        for timer in config.get('timers', {}).values():
            if cat := timer.get('category'):
                categories.add(cat)
        
        # Filter and sort categories based on current input
        filtered = [
            cat for cat in categories 
            if current.lower() in cat.lower()
        ]
        filtered.sort()
        
        return [
            app_commands.Choice(name=cat, value=cat)
            for cat in filtered[:25]  # Discord limits to 25 choices
        ]
    
    