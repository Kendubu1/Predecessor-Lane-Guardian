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
    VALID_LANG_ACCENT_PAIRS,
    EDGE_TTS_VOICES,
    VOICE_PRESETS
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
        # Guard against DM usage
        if not interaction.guild:
            logger.warning(f"Permission denied: {interaction.user.id} tried to use admin command in DM")
            return False

        # Server owner always has permission
        if interaction.user.id == interaction.guild.owner_id:
            return True

        # Check if user has Discord's Administrator permission (auto-grant)
        if interaction.user.guild_permissions.administrator:
            logger.debug(f"Permission granted via Discord Administrator: {interaction.user.id} in guild {interaction.guild.id}")
            return True

        # Check configured admin users and roles
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        settings = config.get('settings', {})

        # Combine admin_users, secondary_owners, and bot_inviter
        authorized_users = set(settings.get('admin_users', []))
        authorized_users.update(settings.get('secondary_owners', []))

        # Add bot inviter if recorded
        bot_inviter = settings.get('bot_inviter')
        if bot_inviter:
            authorized_users.add(bot_inviter)

        if interaction.user.id in authorized_users:
            return True

        # Check role-based permissions (custom admin roles)
        admin_roles = set(settings.get('admin_roles', []))
        user_role_ids = {role.id for role in interaction.user.roles}

        if admin_roles & user_role_ids:  # Set intersection
            return True

        # Log denial for debugging
        logger.debug(
            f"Permission denied: user={interaction.user.id} ({interaction.user.name}) "
            f"guild={interaction.guild.id} command={interaction.command.name if interaction.command else 'unknown'}"
        )
        return False

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
                    'secondary_owners': [],
                    'bot_inviter': None,
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

            # Secondary owners validation
            secondary_owners = settings.get('secondary_owners', [])
            if isinstance(secondary_owners, list):
                sanitized['settings']['secondary_owners'] = [
                    int(user_id) for user_id in secondary_owners
                    if str(user_id).isdigit()
                ]

            # Bot inviter validation
            bot_inviter = settings.get('bot_inviter')
            if bot_inviter is not None and str(bot_inviter).isdigit():
                sanitized['settings']['bot_inviter'] = int(bot_inviter)
            else:
                sanitized['settings']['bot_inviter'] = None

            # TTS settings validation
            tts_settings = settings.get('tts_settings', {})
            if not isinstance(tts_settings, dict):
                tts_settings = {}

            # Voice name validation (Edge-TTS)
            voice_name = str(tts_settings.get('voice_name', 'en-IN-NeerjaNeural'))
            if voice_name and isinstance(voice_name, str):
                sanitized['settings']['tts_settings']['voice_name'] = voice_name
            else:
                sanitized['settings']['tts_settings']['voice_name'] = 'en-IN-NeerjaNeural'

            # Language and accent validation (kept for backwards compatibility)
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

    @app_commands.command(name="voice_preset")
    @app_commands.describe(
        preset="Choose a voice preset (easy selection)"
    )
    async def voice_preset(self, interaction: discord.Interaction, preset: str):
        """Change voice using a preset (recommended for quick setup)."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify settings!", ephemeral=True)
            return

        # Validate preset
        if preset not in VOICE_PRESETS:
            await interaction.response.send_message(
                f"Invalid preset. Use autocomplete to see available presets.",
                ephemeral=True
            )
            return

        preset_config = VOICE_PRESETS[preset]

        # Update all TTS settings from preset
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.tts_settings.voice_name',
            preset_config['voice_name']
        )
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.tts_settings.speed',
            preset_config['speed']
        )
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.tts_settings.pitch',
            preset_config['pitch']
        )

        # Create response embed
        embed = discord.Embed(
            title="Voice Preset Applied",
            description=f"✅ {preset_config['description']}",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Preset",
            value=f"`{preset}`",
            inline=True
        )
        embed.add_field(
            name="Speed",
            value=f"{preset_config['speed']}x",
            inline=True
        )
        embed.add_field(
            name="Pitch",
            value=f"{preset_config['pitch']}x",
            inline=True
        )

        embed.set_footer(text="Use /pred test_voice to hear it | Use /pred set_tts for fine-tuning")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @voice_preset.autocomplete('preset')
    async def preset_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for voice presets."""
        # Filter presets based on current input
        filtered = [
            (preset_id, config['description'])
            for preset_id, config in VOICE_PRESETS.items()
            if current.lower() in preset_id.lower() or current.lower() in config['description'].lower()
        ]

        # Sort to show Indian presets first
        filtered.sort(key=lambda x: (
            0 if 'indian' in x[0].lower() or 'hindi' in x[0].lower() else 1,
            1 if 'esports' in x[0].lower() or 'hype' in x[0].lower() else 2,
            x[0]
        ))

        return [
            app_commands.Choice(name=description, value=preset_id)
            for preset_id, description in filtered[:25]
        ]

    @app_commands.command(name="set_voice")
    @app_commands.describe(
        voice="Choose a specific voice (advanced)"
    )
    async def set_voice(self, interaction: discord.Interaction, voice: str):
        """Change the TTS voice (advanced - use /pred voice_preset for easier setup)."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify settings!", ephemeral=True)
            return

        # Validate voice name
        if voice not in EDGE_TTS_VOICES:
            await interaction.response.send_message(
                f"Invalid voice. Use `/pred set_voice` with autocomplete to see available voices.",
                ephemeral=True
            )
            return

        # Update voice setting
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.tts_settings.voice_name',
            voice
        )

        # Create response embed
        embed = discord.Embed(
            title="Voice Changed",
            description=f"✅ Voice set to: **{EDGE_TTS_VOICES[voice]}**",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Voice ID",
            value=f"`{voice}`",
            inline=False
        )

        embed.set_footer(text="Use /pred test_voice to hear the new voice | Tip: Use /pred voice_preset for easier setup")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @set_voice.autocomplete('voice')
    async def voice_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for available voices."""
        # Filter voices based on current input
        filtered = [
            (voice_id, description)
            for voice_id, description in EDGE_TTS_VOICES.items()
            if current.lower() in voice_id.lower() or current.lower() in description.lower()
        ]

        # Sort to show Indian voices first
        filtered.sort(key=lambda x: (
            0 if 'Indian' in x[1] or 'Hindi' in x[1] else 1,
            x[1]
        ))

        return [
            app_commands.Choice(name=description, value=voice_id)
            for voice_id, description in filtered[:25]  # Discord limits to 25 choices
        ]

    @app_commands.command(name="set_tts")
    @app_commands.describe(
        speed="Voice speed (0.5 = half speed, 1.0 = normal, up to 2.0 = double speed)",
        pitch="Voice pitch (0.5 = low, 1.0 = normal, 2.0 = high)",
        warning_time="Warning time in seconds"
    )
    async def set_tts(self, interaction: discord.Interaction,
                    speed: Optional[float] = None,
                    pitch: Optional[float] = None,
                    warning_time: Optional[int] = None):
        """Configure TTS speed, pitch, and timing settings."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify settings!", ephemeral=True)
            return

        # Get current settings first
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        current_settings = config['settings'].get('tts_settings', {})

        # Prepare new settings, starting with current settings
        settings = current_settings.copy()

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

        # Validate pitch and update
        if pitch is not None:
            if 0.5 <= pitch <= 2.0:
                settings['pitch'] = pitch
            else:
                await interaction.response.send_message(
                    "Pitch must be between 0.5 (low) and 2.0 (high)",
                    ephemeral=True
                )
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

        # Get current voice
        voice_id = settings.get('voice_name', 'en-IN-NeerjaNeural')
        voice_name = EDGE_TTS_VOICES.get(voice_id, voice_id)

        embed.add_field(
            name="Current Voice",
            value=voice_name,
            inline=False
        )
        embed.add_field(
            name="Speed",
            value=f"{settings.get('speed', 1.0)}x",
            inline=True
        )
        embed.add_field(
            name="Pitch",
            value=f"{settings.get('pitch', 1.0)}x",
            inline=True
        )
        if warning_time is not None:
            embed.add_field(
                name="Warning Time",
                value=f"{settings.get('warning_time', 30)}s",
                inline=True
            )

        embed.set_footer(text="Use /pred set_voice to change the voice")

        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @app_commands.command(name="settings")
    async def settings(self, interaction: discord.Interaction):
        """Show the current server settings."""
        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        settings = config.get('settings', {})
        embed = discord.Embed(title="Server Settings", color=discord.Color.blue())

        embed.add_field(name="Volume", value=f"{settings.get('volume', 1.0):.1f}", inline=True)

        admin_roles = [f"<@&{rid}>" for rid in settings.get('admin_roles', [])]
        admin_users = [f"<@{uid}>" for uid in settings.get('admin_users', [])]
        bot_inviter = settings.get('bot_inviter')

        embed.add_field(name="Admin Roles", value=', '.join(admin_roles) if admin_roles else "None", inline=False)
        embed.add_field(name="Admin Users", value=', '.join(admin_users) if admin_users else "None", inline=False)

        if bot_inviter:
            embed.add_field(name="Bot Inviter", value=f"<@{bot_inviter}>", inline=False)

        tts = settings.get('tts_settings', {})
        voice_name = tts.get('voice_name', 'en-IN-NeerjaNeural')
        speed = tts.get('speed', 1.0)
        pitch = tts.get('pitch', 1.0)
        embed.add_field(
            name="TTS Voice",
            value=f"🎤 {voice_name}\n⚡ Speed: {speed}x | 🎵 Pitch: {pitch}x",
            inline=False
        )

        embed.set_footer(text="💡 Users with Discord's Administrator permission automatically have bot admin access")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_volume")
    async def set_volume(self, interaction: discord.Interaction, volume: float):
        """Set the announcement volume (0.0 - 1.0)."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify settings!", ephemeral=True)
            return

        volume = max(0.0, min(1.0, volume))
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.volume',
            volume
        )

        await interaction.response.send_message(f"Volume set to {volume:.1f}", ephemeral=True)

    @app_commands.command(name="test_voice")
    async def test_voice(self, interaction: discord.Interaction, message: Optional[str] = "This is a test"):
        """Play a test voice line using current settings."""
        if not interaction.user.voice:
            await interaction.response.send_message("You need to be in a voice channel!", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        voice_client = await self.bot.voice_service.ensure_voice_client(voice_channel)
        config = self.bot.config_manager.get_server_config(interaction.guild.id)

        await interaction.response.send_message("Playing test message...", ephemeral=True)
        await self.bot.voice_service.play_announcement(voice_client, message, config['settings'])

    @app_commands.command(name="remove_admin")
    async def remove_admin(self, interaction: discord.Interaction, user: discord.User):
        """Remove a user from bot admins."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify admin users!", ephemeral=True)
            return

        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        admin_users = config['settings'].get('admin_users', [])

        if user.id not in admin_users:
            await interaction.response.send_message(f"{user.name} is not an admin!", ephemeral=True)
            return

        admin_users.remove(user.id)
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.admin_users',
            admin_users
        )

        await interaction.response.send_message(f"Removed {user.name} from bot admins.", ephemeral=True)

    @app_commands.command(name="add_admin_role")
    async def add_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        """Add a role as bot admin."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify admin roles!", ephemeral=True)
            return

        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        admin_roles = config['settings'].get('admin_roles', [])

        if role.id in admin_roles:
            await interaction.response.send_message(f"{role.name} is already an admin role!", ephemeral=True)
            return

        admin_roles.append(role.id)
        self.bot.config_manager.update_server_setting(
            interaction.guild.id,
            'settings.admin_roles',
            admin_roles
        )

        await interaction.response.send_message(f"Added {role.name} as an admin role.", ephemeral=True)

    @app_commands.command(name="sync_admins")
    async def sync_admins(self, interaction: discord.Interaction):
        """Manually sync Discord administrators to bot admin list."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to sync admins!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Sync Discord admins
            new_admins = self.bot.config_manager.sync_discord_admins(interaction.guild)

            # Try to detect bot inviter
            await self.bot._detect_bot_inviter(interaction.guild)

            # Get current admin list for display
            config = self.bot.config_manager.get_server_config(interaction.guild.id)
            settings = config.get('settings', {})
            admin_users = settings.get('admin_users', [])
            bot_inviter = settings.get('bot_inviter')

            embed = discord.Embed(
                title="Admin Sync Complete",
                color=discord.Color.green()
            )

            if new_admins > 0:
                embed.description = f"✅ Added {new_admins} new Discord administrator(s) to bot admin list"
            else:
                embed.description = "✅ All Discord administrators are already synced"

            embed.add_field(
                name="Total Bot Admins",
                value=str(len(admin_users)),
                inline=True
            )

            if bot_inviter:
                embed.add_field(
                    name="Bot Inviter",
                    value=f"<@{bot_inviter}>",
                    inline=True
                )

            embed.set_footer(text="Bot automatically syncs Discord admins daily")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in sync_admins command: {e}")
            await interaction.followup.send(
                f"Error syncing admins: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="edit_timer")
    @app_commands.choices(category=[
        app_commands.Choice(name=cat.name.title(), value=cat.value)
        for cat in TimerCategory
    ])
    async def edit_timer(self, interaction: discord.Interaction,
                         name: str, time: str, message: Optional[str] = None,
                         category: str = TimerCategory.REMINDER.value):
        """Edit an existing timer."""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("You don't have permission to modify timers!", ephemeral=True)
            return

        config = self.bot.config_manager.get_server_config(interaction.guild.id)
        timer = config.get('timers', {}).get(name)
        if not timer:
            await interaction.response.send_message(f"Timer '{name}' not found", ephemeral=True)
            return

        try:
            minutes, seconds = map(int, time.split(':'))
            total_seconds = minutes * 60 + seconds
        except ValueError:
            await interaction.response.send_message("Invalid time format. Use M:SS (e.g., 5:30)", ephemeral=True)
            return

        messages = timer.get('messages', [])
        if message:
            messages = [message]

        self.bot.config_manager.update_timer(
            interaction.guild.id,
            name,
            total_seconds,
            messages,
            category
        )

        await interaction.response.send_message(f"Timer '{name}' updated", ephemeral=True)

    @app_commands.command(name="start")
    @app_commands.describe(
        time="Game time in M:SS format (defaults to 0:00)",
        mode="Game mode (standard or nitro)"
    )
    async def start(self, interaction: discord.Interaction, time: str = "00:00", mode: str = "standard"):
        """Start the game timer."""
        try:
            if not interaction.user.voice:
                await interaction.response.send_message("You need to be in a voice channel!")
                return

            voice_channel = interaction.user.voice.channel
            await self.bot.voice_service.ensure_voice_client(voice_channel, force_new=True)
            
            self.bot.timer.start(time, mode)
            await interaction.response.send_message(f"Game timer started at {time} in {mode} mode")
            
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
            voice_name = tts_settings.get('voice_name', 'en-IN-NeerjaNeural')

            embed.add_field(
                name="Imported Configuration",
                value=f"• {timer_count} total timers\n"
                      f"• Voice: {voice_name}\n"
                      f"• Speed: {tts_settings['speed']}x\n"
                      f"• Pitch: {tts_settings.get('pitch', 1.0)}x\n"
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
            # First check for voice channel
            if not interaction.user.voice:
                await interaction.response.send_message(
                    "You need to be in a voice channel!", 
                    ephemeral=True
                )
                return

            # Send initial response before attempting voice connection
            await interaction.response.send_message(
                "Connecting to voice channel...", 
                ephemeral=ephemeral
            )

            try:
                voice_channel = interaction.user.voice.channel
                voice_client = await self.bot.voice_service.ensure_voice_client(voice_channel)
                
                # Get server settings and play message
                config = self.bot.config_manager.get_server_config(interaction.guild.id)
                
                # Update message about playing
                await interaction.edit_original_response(
                    content=f"Playing: {message}"
                )
                
                await self.bot.voice_service.play_announcement(
                    voice_client,
                    message,
                    config['settings']
                )
                
            except asyncio.TimeoutError:
                await interaction.edit_original_response(
                    content="Failed to connect to voice channel (timeout). Please try again."
                )
            except Exception as e:
                logger.error(f"Error in voice connection/playback: {e}")
                await interaction.edit_original_response(
                    content=f"Error playing message: {str(e)}"
                )
                
        except Exception as e:
            logger.error(f"Error in say command: {e}")
            # Only try to respond if we haven't already
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"Error: {str(e)}", 
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
    
    
