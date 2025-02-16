import base64
import json
import os
import tempfile
import discord
from discord import app_commands
from typing import Optional, List
import logging
import asyncio
from config import (
    TimerCategory, 
    TTSLanguage, 
    TTSAccent, 
    TTSSpeed, 
    VALID_LANG_ACCENT_PAIRS
)

logger = logging.getLogger('PredTimer.Commands')

class GameCommands(app_commands.Group):
    """Handles all game-related commands for the bot."""
    
    def __init__(self, bot):
        super().__init__(name="pred", description="pred game timer commands")
        self.bot = bot

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use admin commands."""
        if interaction.user.id == interaction.guild.owner_id:
            return True
            
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        admin_roles = config.get('settings', {}).get('admin_roles', [])
        return any(role.id in admin_roles for role in interaction.user.roles)
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use admin commands."""
        # Get the server config
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        
        # Get or initialize the admin users list
        admin_users = config['settings'].get('admin_users', [])
        
        # Check if this is a first-time interaction (no admins set)
        if not admin_users and not config['settings'].get('admin_roles', []):
            # First person to use an admin command becomes admin
            admin_users = [interaction.user.id]
            config['settings']['admin_users'] = admin_users
            self.bot.config_manager.update_server_setting(
                interaction.guild.id,
                'settings.admin_users',
                admin_users
            )
            return True

        # Check if user is server owner, in admin roles, or in admin users list
        return (interaction.user.id == interaction.guild.owner_id or
                interaction.user.id in admin_users or
                any(role.id in config['settings'].get('admin_roles', []) 
                    for role in interaction.user.roles))

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

    @app_commands.command(name="remove_admin")
    async def remove_admin(self, interaction: discord.Interaction, user: discord.User):
        """Remove a user from bot admins."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message(
                "You don't have permission to modify admin users!",
                ephemeral=True
            )
            return

        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        admin_users = config['settings'].get('admin_users', [])
        
        if user.id not in admin_users:
            await interaction.response.send_message(
                f"{user.name} is not an admin!",
                ephemeral=True
            )
            return

        # Prevent removing the last admin
        if len(admin_users) <= 1 and user.id == interaction.user.id:
            await interaction.response.send_message(
                "Cannot remove the last admin. Add another admin first.",
                ephemeral=True
            )
            return

        admin_users.remove(user.id)
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.admin_users',
            admin_users
        )
        
        await interaction.response.send_message(
            f"Removed {user.name} from bot admins.",
            ephemeral=True
        )
        
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
            else:
                # Reset to defaults if invalid
                sanitized['settings']['tts_settings']['language'] = 'en'
                sanitized['settings']['tts_settings']['accent'] = 'co.in'

            # Other TTS settings validation
            try:
                warning_time = int(tts_settings.get('warning_time', 30))
                sanitized['settings']['tts_settings']['warning_time'] = max(0, min(60, warning_time))
            except (ValueError, TypeError):
                sanitized['settings']['tts_settings']['warning_time'] = 30

            try:
                speed = float(tts_settings.get('speed', 1.0))
                sanitized['settings']['tts_settings']['speed'] = max(0.5, min(1.5, speed))
            except (ValueError, TypeError):
                sanitized['settings']['tts_settings']['speed'] = 1.0

            # Timers validation
            timers = config_data.get('timers', {})
            if not isinstance(timers, dict):
                return False, "Timers section must be a dictionary", {}

            for name, timer in timers.items():
                if not isinstance(timer, dict):
                    continue

                required_timer_keys = {'time', 'message', 'category'}
                if not all(key in timer for key in required_timer_keys):
                    continue

                try:
                    time_value = int(timer['time'])
                    if not 0 <= time_value <= 3600:  # Max 1 hour
                        continue
                        
                    message = str(timer['message']).strip()
                    if not message or len(message) > 200:  # Message length limit
                        continue

                    category = str(timer['category'])
                    if category not in [cat.value for cat in TimerCategory]:
                        continue

                    sanitized['timers'][str(name)] = {
                        'time': time_value,
                        'message': message,
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

    @app_commands.command(name="import_config")
    @app_commands.describe(
        config_code="The configuration code to import",
        merge="Whether to merge with existing configuration or replace entirely",
        keep_existing_timers="Keep existing timers when importing (only with merge=True)"
    )
    async def import_config(self, 
                          interaction: discord.Interaction, 
                          config_code: str,
                          merge: bool = True,
                          keep_existing_timers: bool = True):
        """Import a server configuration."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message(
                "You need admin permissions to import configurations!",
                ephemeral=True
            )
            return

        try:
            # Decode and parse the configuration
            decoded_bytes = base64.b64decode(config_code)
            config_data = json.loads(decoded_bytes.decode())
            
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
                      f"• Warning Time: {tts_settings['warning_time']}s\n"
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
                "Error importing configuration. Please check the format and try again.",
                ephemeral=True
            )

    @app_commands.command(name="start")
    async def start(self, interaction: discord.Interaction, time: str):
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

            self.bot.config_manager.update_timer(
                interaction.guild.id,
                name,
                total_seconds,
                message,
                category
            )

            await interaction.response.send_message(
                f"Timer '{name}' added for {time} with message: {message}"
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
                embed.add_field(
                    name=f"{minutes:02d}:{seconds:02d} - {name}",
                    value=f"Category: {timer.get('category', 'uncategorized')}\nMessage: {timer['message']}",
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

    @app_commands.command(name="set_tts")
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
        
        # Validate language and accent combination
        if language and accent:
            if (language, accent) not in VALID_LANG_ACCENT_PAIRS:
                error_message = f"Invalid language ({language}) and accent ({accent}) combination. Please check the available combinations."
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
        if speed is not None:
            settings['speed'] = max(0.5, min(1.5, speed))
        
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
        
        # Get updated settings
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        tts_settings = config['settings']['tts_settings']
        
        # Get the display name for the language-accent combination
        lang_accent_name = VALID_LANG_ACCENT_PAIRS.get(
            (tts_settings.get('language'), tts_settings.get('accent')),
            f"{tts_settings.get('language', 'en')} ({tts_settings.get('accent', 'co.in')})"
        )
        
        embed.add_field(
            name="Voice Settings",
            value=f"Language/Accent: {lang_accent_name}",
            inline=False
        )
        embed.add_field(
            name="Warning Time", 
            value=f"{tts_settings.get('warning_time', 30)}s", 
            inline=True
        )
        embed.add_field(
            name="Speed", 
            value=f"{tts_settings.get('speed', 1.0)}x", 
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="set_volume")
    async def set_volume(self, interaction: discord.Interaction, volume: float):
        """Set the volume for voice announcements (0.0 - 1.0)."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify settings!")
            return

        volume = max(0.0, min(1.0, volume))
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.volume',
            volume
        )
        await interaction.response.send_message(f"Volume set to {volume}")

    @app_commands.command(name="add_admin_role")
    async def add_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        """Add a role that can modify bot configuration."""
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Only the server owner can modify admin roles!")
            return

        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        admin_roles = config.get('settings', {}).get('admin_roles', [])
        
        if role.id not in admin_roles:
            admin_roles.append(role.id)
            self.bot.config_manager.update_server_setting(
                interaction.guild.id,
                'settings.admin_roles',
                admin_roles
            )
            await interaction.response.send_message(f"Added {role.name} as an admin role")
        else:
            await interaction.response.send_message(f"{role.name} is already an admin role")

    @app_commands.command(name="test_voice")
    async def test_voice(self, interaction: discord.Interaction, message: Optional[str] = None):
        """Test the current TTS voice settings."""
        try:
            # Check if timer is active
            if self.bot.timer.is_active:
                await interaction.response.send_message(
                    "Cannot test TTS while game timer is running. Stop the timer first!", 
                    ephemeral=True
                )
                return

            if not interaction.user.voice:
                await interaction.response.send_message("You need to be in a voice channel!")
                return

            voice_channel = interaction.user.voice.channel
            voice_client = await self.bot.voice_service.ensure_voice_client(voice_channel)
            
            # Use default test message if none provided
            test_message = message or "This is a test of the current voice settings for Predecessor Timer"
            
            await interaction.response.send_message("Playing test message...")
            
            # Get server settings and play test message
            config = self.bot.config_manager.get_server_config(interaction.guild.id)
            await self.bot.voice_service.play_announcement(
                voice_client,
                test_message,
                config['settings']
            )
            
            # Cleanup after test
            await asyncio.sleep(5)  # Wait for message to finish
            if not self.bot.timer.is_active:  # Only disconnect if timer isn't running
                await self.bot.voice_service.cleanup_voice_clients(interaction.guild)
            
        except Exception as e:
            logger.error(f"Error in test_voice: {e}")
            await interaction.response.send_message(f"Error testing voice: {str(e)}")

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
            
            # Add timer count and settings summary
            timer_count = len(config.get('timers', {}))
            embed.add_field(
                name="Configuration Summary",
                value=f"• {timer_count} timers configured\n"
                      f"• Language: {config['settings']['tts_settings'].get('language', 'en')}\n"
                      f"• Accent: {config['settings']['tts_settings'].get('accent', 'co.in')}",
                inline=False
            )

            # Create a temporary file with the config
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
                temp_file.write(config_str)
                temp_file.flush()
                
                # Send the embed with the file
                await interaction.response.send_message(
                    embed=embed,
                    file=discord.File(temp_file.name, filename=f"config_{interaction.guild.name}.json"),
                    ephemeral=True  # Only visible to the user who requested it
                )

            # Clean up the temporary file
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

            # Read the file content
            config_str = await file.read()
            config_str = config_str.decode('utf-8')

            # Parse JSON
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
                      f"• Warning Time: {tts_settings['warning_time']}s\n"
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
    
    @app_commands.command(name="settings")
    async def show_settings(self, interaction: discord.Interaction):
        """Show current server settings."""
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        settings = config.get('settings', {})
        
        embed = discord.Embed(
            title="Server Settings",
            color=discord.Color.blue()
        )
        
        # Volume settings
        embed.add_field(
            name="Volume",
            value=f"{settings.get('volume', 1.0):.1f}",
            inline=True
        )
        
        # TTS settings
        tts_settings = settings.get('tts_settings', {})
        
        # Get the display name for the language-accent combination
        lang_accent_name = VALID_LANG_ACCENT_PAIRS.get(
            (tts_settings.get('language'), tts_settings.get('accent')),
            f"{tts_settings.get('language', 'en')} ({tts_settings.get('accent', 'co.in')})"
        )
        
        embed.add_field(
            name="Voice Settings",
            value=f"Language/Accent: {lang_accent_name}",
            inline=True
        )
        
        # Admin roles
        admin_roles = settings.get('admin_roles', [])
        role_names = []
        for role_id in admin_roles:
            role = interaction.guild.get_role(role_id)
            if role:
                role_names.append(role.name)
        
        if role_names:
            embed.add_field(
                name="Admin Roles",
                value="\n".join(role_names),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

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

    @set_tts.autocomplete('speed')
    async def speed_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for TTS speed."""
        speeds = [
            (speed.value, f"{speed.name.title()} ({speed.value}x)")
            for speed in TTSSpeed
        ]
        
        # Convert current to string for comparison
        current_str = str(current).lower()
        
        # Filter based on current input
        filtered = [
            (value, name) for value, name in speeds
            if current_str in str(value) or current_str in name.lower()
        ]
        
        return [
            app_commands.Choice(name=name, value=float(value))
            for value, name in filtered[:25]
        ]