"""Slash commands for Lane Guardian, all under /pred."""
import asyncio
import io
import json
import logging
from typing import List, Optional

import discord
from discord import app_commands

from config import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_VOICE,
    EDGE_TTS_VOICES,
    PITCH_CHOICES,
    SPEED_CHOICES,
    TimerCategory,
    VALID_LANG_ACCENT_PAIRS,
    VOICE_PRESETS,
    describe_pitch,
    describe_speed,
    find_preset,
)
from timer import GameTimer

logger = logging.getLogger('PredTimer.Commands')

PREVIEW_TEXT = "Voice updated. Fangtooth is now online, get ready."
CATEGORY_CHOICES = [
    app_commands.Choice(name=cat.name.replace('_', ' ').title(), value=cat.value)
    for cat in TimerCategory
]


@app_commands.guild_only()
class GameCommands(app_commands.Group):
    """All /pred subcommands."""

    def __init__(self, bot):
        super().__init__(name="pred", description="Predecessor game timer commands")
        self.bot = bot
        logger.info(f"GameCommands registered {len(self.commands)} subcommands")

    # ------------------------------------------------------------ helpers
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """True if the user may change bot settings in this server."""
        if not interaction.guild:
            return False
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if interaction.user.guild_permissions.administrator:
            return True

        settings = self.bot.config_manager.get_server_config(interaction.guild.id).get('settings', {})
        authorized_users = set(settings.get('admin_users', []))
        authorized_users.update(settings.get('secondary_owners', []))
        if settings.get('bot_inviter'):
            authorized_users.add(settings['bot_inviter'])
        if interaction.user.id in authorized_users:
            return True

        admin_roles = set(settings.get('admin_roles', []))
        if admin_roles & {role.id for role in interaction.user.roles}:
            return True

        logger.debug(f"Permission denied: user={interaction.user.id} guild={interaction.guild.id}")
        return False

    async def _deny(self, interaction: discord.Interaction, what: str = "change settings") -> None:
        await interaction.response.send_message(
            f"You don't have permission to {what}. Ask a server admin or a bot admin.",
            ephemeral=True,
        )

    def _settings(self, interaction: discord.Interaction) -> dict:
        return self.bot.config_manager.get_server_config(interaction.guild.id)['settings']

    async def _preview_voice(self, interaction: discord.Interaction, text: str = PREVIEW_TEXT) -> bool:
        """Play a short sample if the user is in a voice channel. Returns True if it played."""
        voice = interaction.user.voice
        if not voice or not voice.channel:
            return False
        try:
            voice_client = await self.bot.voice_service.ensure_voice_client(voice.channel)
            await self.bot.voice_service.play_announcement(voice_client, text, self._settings(interaction))
            return True
        except Exception as e:
            logger.warning(f"Voice preview failed in guild {interaction.guild.id}: {e}")
            return False

    def _voice_embed(self, interaction: discord.Interaction, title: str, previewed: bool) -> discord.Embed:
        tts = self._settings(interaction).get('tts_settings', {})
        voice_id = tts.get('voice_name', DEFAULT_VOICE)
        preset = find_preset(tts)
        embed = discord.Embed(title=title, color=discord.Color.green())
        embed.add_field(name="Voice", value=EDGE_TTS_VOICES.get(voice_id, voice_id), inline=False)
        embed.add_field(name="Preset", value=f"`{preset}`" if preset else "Custom", inline=True)
        embed.add_field(name="Speed", value=describe_speed(float(tts.get('speed', DEFAULT_SPEED))), inline=True)
        embed.add_field(name="Pitch", value=describe_pitch(float(tts.get('pitch', DEFAULT_PITCH))), inline=True)
        if previewed:
            embed.set_footer(text="Playing a sample in your voice channel.")
        else:
            embed.set_footer(text="Join a voice channel and run /pred test_voice to hear it.")
        return embed

    # ------------------------------------------------------------ validation
    def validate_config(self, config_data: dict) -> tuple[bool, str, dict]:
        """Validate and sanitize an imported config. Returns (ok, error, sanitized)."""
        try:
            if not isinstance(config_data, dict):
                return False, "Configuration must be a JSON object", {}
            if not {'settings', 'timers'} <= set(config_data):
                return False, "Configuration needs both 'settings' and 'timers' sections", {}

            sanitized = {
                'settings': {
                    'volume': 1.0,
                    'admin_roles': [],
                    'admin_users': [],
                    'secondary_owners': [],
                    'bot_inviter': None,
                    'tts_settings': {
                        'voice_name': DEFAULT_VOICE,
                        'language': 'en',
                        'accent': 'co.in',
                        'warning_time': 0,
                        'speed': DEFAULT_SPEED,
                        'pitch': DEFAULT_PITCH,
                        'word_gap': 0.1,
                        'emphasis_volume': 1.2,
                        'use_phonetics': False,
                        'capitalize_proper_nouns': True,
                        'number_to_words': True,
                        'custom_pronunciations': {},
                    },
                },
                'timers': {},
            }

            settings = config_data.get('settings', {})
            if not isinstance(settings, dict):
                return False, "Settings section must be an object", {}

            try:
                sanitized['settings']['volume'] = max(0.0, min(2.0, float(settings.get('volume', 1.0))))
            except (ValueError, TypeError):
                pass

            for key in ('admin_roles', 'admin_users', 'secondary_owners'):
                values = settings.get(key, [])
                if isinstance(values, list):
                    sanitized['settings'][key] = [int(v) for v in values if str(v).isdigit()]

            bot_inviter = settings.get('bot_inviter')
            if bot_inviter is not None and str(bot_inviter).isdigit():
                sanitized['settings']['bot_inviter'] = int(bot_inviter)

            tts_in = settings.get('tts_settings', {})
            if not isinstance(tts_in, dict):
                tts_in = {}
            tts_out = sanitized['settings']['tts_settings']

            voice_name = str(tts_in.get('voice_name', DEFAULT_VOICE))
            tts_out['voice_name'] = voice_name if voice_name in EDGE_TTS_VOICES else DEFAULT_VOICE

            language = str(tts_in.get('language', 'en'))
            accent = str(tts_in.get('accent', 'co.in'))
            if (language, accent) in VALID_LANG_ACCENT_PAIRS:
                tts_out['language'], tts_out['accent'] = language, accent

            try:
                tts_out['warning_time'] = max(0, min(60, int(tts_in.get('warning_time', 0))))
            except (ValueError, TypeError):
                pass
            try:
                tts_out['speed'] = max(0.5, min(2.0, float(tts_in.get('speed', DEFAULT_SPEED))))
            except (ValueError, TypeError):
                pass
            try:
                tts_out['pitch'] = max(0.5, min(2.0, float(tts_in.get('pitch', DEFAULT_PITCH))))
            except (ValueError, TypeError):
                pass

            pron = tts_in.get('custom_pronunciations', {})
            if isinstance(pron, dict):
                tts_out['custom_pronunciations'] = {
                    str(k)[:50]: str(v)[:50] for k, v in pron.items() if str(k).strip()
                }

            timers = config_data.get('timers', {})
            if not isinstance(timers, dict):
                return False, "Timers section must be an object", {}

            for name, timer in timers.items():
                if not isinstance(timer, dict):
                    continue
                messages = timer.get('messages', [timer.get('message', 'Timer event')])
                if isinstance(messages, str):
                    messages = [messages]
                elif not isinstance(messages, list):
                    continue
                try:
                    time_value = int(timer['time'])
                except (ValueError, TypeError, KeyError):
                    continue
                if not 0 <= time_value <= 3600:
                    continue

                valid_messages = [str(m).strip() for m in messages if str(m).strip() and len(str(m)) <= 200]
                if not valid_messages:
                    valid_messages = ['Timer event']

                category = str(timer.get('category', TimerCategory.REMINDER.value))
                if category not in {cat.value for cat in TimerCategory}:
                    category = TimerCategory.REMINDER.value

                sanitized['timers'][str(name)[:50]] = {
                    'time': time_value,
                    'messages': valid_messages,
                    'category': category,
                }

            if not sanitized['timers']:
                return False, "No valid timers found in configuration", {}

            return True, "", sanitized
        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False, f"Error validating configuration: {e}", {}

    # ============================================================ game timer
    @app_commands.command(name="start", description="Start the game timer (join a voice channel first)")
    @app_commands.describe(
        time="Current in-game time as M:SS. Leave blank when minions spawn (0:00).",
        mode="Which timer set to use",
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Standard", value="standard"),
        app_commands.Choice(name="Nitro", value="nitro"),
    ])
    async def start(self, interaction: discord.Interaction, time: str = "0:00", mode: str = "standard"):
        voice = interaction.user.voice
        if not voice or not voice.channel:
            await interaction.response.send_message("Join a voice channel first, then run `/pred start`.", ephemeral=True)
            return
        try:
            seconds = GameTimer.parse_time(time)
        except ValueError:
            await interaction.response.send_message("Time must look like `M:SS`, for example `0:00` or `4:30`.", ephemeral=True)
            return

        # Joining voice can take longer than Discord's 3 second reply window.
        await interaction.response.defer()
        try:
            await self.bot.voice_service.ensure_voice_client(voice.channel)
        except asyncio.TimeoutError:
            await interaction.followup.send("Couldn't connect to your voice channel (timed out). Please try again.")
            return
        except Exception as e:
            logger.error(f"[{interaction.guild.id}] Voice connect failed: {e}")
            await interaction.followup.send(f"Couldn't connect to voice: {e}")
            return

        timer = self.bot.get_timer(interaction.guild.id)
        timer.start(time, mode)

        embed = discord.Embed(
            title="⏱️ Game timer started",
            description=f"Game time **{GameTimer.format_time(seconds)}** · {mode.title()} mode\n"
                        f"Announcing in {voice.channel.mention}",
            color=discord.Color.green(),
        )
        embed.set_footer(text="Use /pred status to see upcoming callouts, /pred stop to end.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stop", description="Stop the game timer and leave voice")
    async def stop(self, interaction: discord.Interaction):
        timer = self.bot.get_timer(interaction.guild.id, create=False)
        was_active = bool(timer and timer.is_active)
        if timer:
            timer.stop()
        try:
            await self.bot.voice_service.cleanup_voice_clients(interaction.guild)
        except Exception as e:
            logger.warning(f"[{interaction.guild.id}] Error leaving voice: {e}")
        await interaction.response.send_message(
            "Game timer stopped. GG!" if was_active else "No timer was running. Left voice if I was there."
        )

    @app_commands.command(name="status", description="Show the current game time and upcoming callouts")
    async def status(self, interaction: discord.Interaction):
        timer = self.bot.get_timer(interaction.guild.id, create=False)
        voice_client = interaction.guild.voice_client

        if not timer or not timer.is_active:
            await interaction.response.send_message(
                "No timer running. Join a voice channel and use `/pred start` when minions spawn.",
                ephemeral=True,
            )
            return

        now = timer.get_game_time()
        events = self.bot.config_manager.get_server_timers(interaction.guild.id, mode=timer.mode)
        upcoming = sorted(
            ((e['time'], name) for name, e in events.items()
             if e.get('time', 0) >= now and name not in timer.announced_events),
        )[:5]

        embed = discord.Embed(title="⏱️ Game status", color=discord.Color.blue())
        embed.add_field(name="Game time", value=f"**{GameTimer.format_time(now)}**", inline=True)
        embed.add_field(name="Mode", value=timer.mode.title(), inline=True)
        embed.add_field(
            name="Voice",
            value=voice_client.channel.mention if voice_client and voice_client.is_connected() else "Not connected",
            inline=True,
        )
        if upcoming:
            embed.add_field(
                name="Next callouts",
                value="\n".join(f"`{GameTimer.format_time(t)}` {name.replace('_', ' ')}" for t, name in upcoming),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================ speaking
    @app_commands.command(name="say", description="Speak a message in your voice channel")
    @app_commands.describe(message="What to say", ephemeral="Only show the confirmation to you")
    async def say(self, interaction: discord.Interaction, message: app_commands.Range[str, 1, 300],
                  ephemeral: bool = True):
        voice = interaction.user.voice
        if not voice or not voice.channel:
            await interaction.response.send_message("Join a voice channel first.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=ephemeral)
        try:
            voice_client = await self.bot.voice_service.ensure_voice_client(voice.channel)
            await interaction.followup.send(f"🗣️ {message}", ephemeral=ephemeral)
            await self.bot.voice_service.play_announcement(voice_client, message, self._settings(interaction))
        except asyncio.TimeoutError:
            await interaction.followup.send("Couldn't connect to voice (timed out). Please try again.", ephemeral=True)
        except Exception as e:
            logger.error(f"[{interaction.guild.id}] Error in say: {e}")
            await interaction.followup.send(f"Couldn't play that: {e}", ephemeral=True)

    @app_commands.command(name="test_voice", description="Play a sample line with the current voice settings")
    @app_commands.describe(message="Custom text to speak (optional)")
    async def test_voice(self, interaction: discord.Interaction, message: Optional[app_commands.Range[str, 1, 300]] = None):
        voice = interaction.user.voice
        if not voice or not voice.channel:
            await interaction.response.send_message("Join a voice channel first.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        played = await self._preview_voice(interaction, message or PREVIEW_TEXT)
        if played:
            await interaction.followup.send(embed=self._voice_embed(interaction, "🔊 Voice test", True), ephemeral=True)
        else:
            await interaction.followup.send("Couldn't play the test line. Check the bot logs.", ephemeral=True)

    # ============================================================ voice settings
    @app_commands.command(name="voice_preset", description="Pick a voice from the list (easiest way to change the voice)")
    @app_commands.describe(preset="Voice preset", preview="Play a sample right away if you're in voice")
    @app_commands.choices(preset=[
        app_commands.Choice(name=cfg['description'], value=name)
        for name, cfg in VOICE_PRESETS.items()
    ])
    async def voice_preset(self, interaction: discord.Interaction, preset: str, preview: bool = True):
        if not await self.check_permissions(interaction):
            await self._deny(interaction)
            return
        cfg = VOICE_PRESETS.get(preset)
        if not cfg:
            await interaction.response.send_message("Unknown preset. Pick one from the list.", ephemeral=True)
            return

        cm = self.bot.config_manager
        gid = interaction.guild.id
        cm.update_server_setting(gid, 'settings.tts_settings.voice_name', cfg['voice_name'])
        cm.update_server_setting(gid, 'settings.tts_settings.speed', cfg['speed'])
        cm.update_server_setting(gid, 'settings.tts_settings.pitch', cfg['pitch'])

        await interaction.response.defer(ephemeral=True)
        played = preview and await self._preview_voice(interaction)
        await interaction.followup.send(embed=self._voice_embed(interaction, "✅ Voice preset applied", played), ephemeral=True)

    @app_commands.command(name="set_voice", description="Choose a specific voice by name (advanced)")
    @app_commands.describe(voice="Start typing to search voices", preview="Play a sample right away if you're in voice")
    async def set_voice(self, interaction: discord.Interaction, voice: str, preview: bool = True):
        if not await self.check_permissions(interaction):
            await self._deny(interaction)
            return
        if voice not in EDGE_TTS_VOICES:
            await interaction.response.send_message("Unknown voice. Use the autocomplete list.", ephemeral=True)
            return

        self.bot.config_manager.update_server_setting(interaction.guild.id, 'settings.tts_settings.voice_name', voice)
        await interaction.response.defer(ephemeral=True)
        played = preview and await self._preview_voice(interaction)
        await interaction.followup.send(embed=self._voice_embed(interaction, "✅ Voice changed", played), ephemeral=True)

    @set_voice.autocomplete('voice')
    async def voice_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        current = current.lower()
        matches = [
            (vid, desc) for vid, desc in EDGE_TTS_VOICES.items()
            if current in vid.lower() or current in desc.lower()
        ]
        matches.sort(key=lambda x: (0 if '-IN-' in x[0] else 1, x[1]))
        return [app_commands.Choice(name=f"{desc} ({vid})"[:100], value=vid) for vid, desc in matches[:25]]

    @app_commands.command(name="set_tts", description="Adjust speed, pitch and how early callouts play")
    @app_commands.describe(
        speed="How fast the voice talks",
        pitch="Voice pitch",
        warning_time="Seconds before an event to announce it (0 = right on time)",
        preview="Play a sample right away if you're in voice",
    )
    @app_commands.choices(
        speed=[app_commands.Choice(name=label, value=value) for value, label in SPEED_CHOICES],
        pitch=[app_commands.Choice(name=label, value=value) for value, label in PITCH_CHOICES],
    )
    async def set_tts(self, interaction: discord.Interaction,
                      speed: Optional[app_commands.Choice[float]] = None,
                      pitch: Optional[app_commands.Choice[float]] = None,
                      warning_time: Optional[app_commands.Range[int, 0, 60]] = None,
                      preview: bool = True):
        if not await self.check_permissions(interaction):
            await self._deny(interaction)
            return
        if speed is None and pitch is None and warning_time is None:
            await interaction.response.send_message(
                "Nothing to change. Pick a speed, pitch or warning time.", ephemeral=True
            )
            return

        cm = self.bot.config_manager
        gid = interaction.guild.id
        if speed is not None:
            cm.update_server_setting(gid, 'settings.tts_settings.speed', float(speed.value))
        if pitch is not None:
            cm.update_server_setting(gid, 'settings.tts_settings.pitch', float(pitch.value))
        if warning_time is not None:
            cm.update_server_setting(gid, 'settings.tts_settings.warning_time', int(warning_time))

        await interaction.response.defer(ephemeral=True)
        played = preview and (speed is not None or pitch is not None) and await self._preview_voice(interaction)
        embed = self._voice_embed(interaction, "✅ TTS settings updated", played)
        embed.add_field(
            name="Warning time",
            value=f"{self._settings(interaction)['tts_settings'].get('warning_time', 0)}s before each event",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="set_volume", description="Set announcement volume as a percentage")
    @app_commands.describe(volume="0 to 200 percent (100 = normal)")
    async def set_volume(self, interaction: discord.Interaction, volume: app_commands.Range[int, 0, 200]):
        if not await self.check_permissions(interaction):
            await self._deny(interaction)
            return
        self.bot.config_manager.update_server_setting(interaction.guild.id, 'settings.volume', volume / 100)
        await interaction.response.send_message(f"🔊 Volume set to {volume}%.", ephemeral=True)

    @app_commands.command(name="settings", description="Show this server's bot settings")
    async def settings(self, interaction: discord.Interaction):
        settings = self._settings(interaction)
        tts = settings.get('tts_settings', {})
        voice_id = tts.get('voice_name', DEFAULT_VOICE)
        preset = find_preset(tts)

        embed = discord.Embed(title="⚙️ Lane Guardian settings", color=discord.Color.blue())
        embed.add_field(
            name="Voice",
            value=(
                f"{EDGE_TTS_VOICES.get(voice_id, voice_id)}\n"
                f"Preset: `{preset}`" + ("" if preset else " (custom)") + "\n"
                f"Speed: {describe_speed(float(tts.get('speed', DEFAULT_SPEED)))} · "
                f"Pitch: {describe_pitch(float(tts.get('pitch', DEFAULT_PITCH)))}\n"
                f"Volume: {round(float(settings.get('volume', 1.0)) * 100)}% · "
                f"Warning: {tts.get('warning_time', 0)}s early"
            ),
            inline=False,
        )

        admin_roles = [f"<@&{rid}>" for rid in settings.get('admin_roles', [])]
        admin_users = [f"<@{uid}>" for uid in settings.get('admin_users', [])]
        embed.add_field(name="Admin roles", value=', '.join(admin_roles) or "None", inline=False)
        embed.add_field(name="Admin users", value=', '.join(admin_users[:20]) or "None", inline=False)
        if settings.get('bot_inviter'):
            embed.add_field(name="Bot inviter", value=f"<@{settings['bot_inviter']}>", inline=False)

        timers = self.bot.config_manager.get_server_timers(interaction.guild.id)
        embed.add_field(name="Timers", value=f"{len(timers)} configured (see `/pred list_timers`)", inline=False)
        embed.set_footer(text="Change the voice with /pred voice_preset · Server admins always have access")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="How to use Lane Guardian")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 Lane Guardian",
            description="Voice callouts for Predecessor objectives and timings.",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="During a game",
            value=(
                "`/pred start` when minions spawn (or `/pred start time:4:30` if you're late)\n"
                "`/pred status` to see what's coming up\n"
                "`/pred stop` when the game ends"
            ),
            inline=False,
        )
        embed.add_field(
            name="Voice",
            value=(
                "`/pred voice_preset` pick a voice from the list\n"
                "`/pred set_tts` speed, pitch and warning time\n"
                "`/pred set_volume` 0 to 200%\n"
                "`/pred test_voice` or `/pred say` to hear it"
            ),
            inline=False,
        )
        embed.add_field(
            name="Timers (admins)",
            value=(
                "`/pred list_timers`, `/pred add_timer`, `/pred edit_timer`, `/pred remove_timer`\n"
                "`/pred export_config` / `/pred import_config` to back up or share"
            ),
            inline=False,
        )
        embed.set_footer(text="The bot leaves voice automatically when the channel empties or after 5 idle minutes.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================ admins
    @app_commands.command(name="add_admin", description="Allow a user to manage the bot")
    async def add_admin(self, interaction: discord.Interaction, user: discord.User):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "manage bot admins")
            return
        admin_users = list(self._settings(interaction).get('admin_users', []))
        if user.id in admin_users:
            await interaction.response.send_message(f"{user.mention} is already a bot admin.", ephemeral=True)
            return
        admin_users.append(user.id)
        self.bot.config_manager.update_server_setting(interaction.guild.id, 'settings.admin_users', admin_users)
        await interaction.response.send_message(f"Added {user.mention} as a bot admin.", ephemeral=True)

    @app_commands.command(name="remove_admin", description="Remove a user from bot admins")
    async def remove_admin(self, interaction: discord.Interaction, user: discord.User):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "manage bot admins")
            return
        admin_users = list(self._settings(interaction).get('admin_users', []))
        if user.id not in admin_users:
            await interaction.response.send_message(f"{user.mention} is not a bot admin.", ephemeral=True)
            return
        admin_users.remove(user.id)
        self.bot.config_manager.update_server_setting(interaction.guild.id, 'settings.admin_users', admin_users)
        await interaction.response.send_message(f"Removed {user.mention} from bot admins.", ephemeral=True)

    @app_commands.command(name="add_admin_role", description="Allow everyone with a role to manage the bot")
    async def add_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "manage admin roles")
            return
        admin_roles = list(self._settings(interaction).get('admin_roles', []))
        if role.id in admin_roles:
            await interaction.response.send_message(f"{role.mention} is already an admin role.", ephemeral=True)
            return
        admin_roles.append(role.id)
        self.bot.config_manager.update_server_setting(interaction.guild.id, 'settings.admin_roles', admin_roles)
        await interaction.response.send_message(f"Added {role.mention} as an admin role.", ephemeral=True)

    @app_commands.command(name="remove_admin_role", description="Remove a role from bot admins")
    async def remove_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "manage admin roles")
            return
        admin_roles = list(self._settings(interaction).get('admin_roles', []))
        if role.id not in admin_roles:
            await interaction.response.send_message(f"{role.mention} is not an admin role.", ephemeral=True)
            return
        admin_roles.remove(role.id)
        self.bot.config_manager.update_server_setting(interaction.guild.id, 'settings.admin_roles', admin_roles)
        await interaction.response.send_message(f"Removed {role.mention} from admin roles.", ephemeral=True)

    @app_commands.command(name="sync_admins", description="Re-scan Discord administrators into the bot admin list")
    async def sync_admins(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "sync admins")
            return
        await interaction.response.defer(ephemeral=True)
        try:
            new_admins = self.bot.config_manager.sync_discord_admins(interaction.guild)
            await self.bot._detect_bot_inviter(interaction.guild)
            settings = self._settings(interaction)
            embed = discord.Embed(
                title="Admin sync complete",
                description=(f"Added {new_admins} new Discord administrator(s)." if new_admins
                             else "All Discord administrators were already synced."),
                color=discord.Color.green(),
            )
            embed.add_field(name="Total bot admins", value=str(len(settings.get('admin_users', []))), inline=True)
            if settings.get('bot_inviter'):
                embed.add_field(name="Bot inviter", value=f"<@{settings['bot_inviter']}>", inline=True)
            embed.set_footer(text="Admins are also synced automatically once a day.")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in sync_admins: {e}")
            await interaction.followup.send(f"Error syncing admins: {e}", ephemeral=True)

    # ============================================================ timers
    @app_commands.command(name="add_timer", description="Add a callout (or add another message to an existing one)")
    @app_commands.describe(name="Short id, e.g. fangtooth_spawn", time="Game time as M:SS", message="What to say",
                           category="Category")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def add_timer(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 50], time: str,
                        message: app_commands.Range[str, 1, 200], category: str = TimerCategory.REMINDER.value):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "add timers")
            return
        try:
            total_seconds = GameTimer.parse_time(time)
        except ValueError:
            await interaction.response.send_message("Time must look like `M:SS`, for example `5:30`.", ephemeral=True)
            return

        name = name.strip().lower().replace(' ', '_')
        existing = self.bot.config_manager.get_server_timers(interaction.guild.id).get(name, {})
        messages = list(existing.get('messages', []))
        if message not in messages:
            messages.append(message)

        self.bot.config_manager.update_timer(interaction.guild.id, name, total_seconds, messages, category)
        await interaction.response.send_message(
            f"Timer `{name}` set for **{GameTimer.format_time(total_seconds)}** "
            f"with {len(messages)} message{'s' if len(messages) != 1 else ''}.",
            ephemeral=True,
        )

    @app_commands.command(name="edit_timer", description="Change a callout's time, message or category")
    @app_commands.describe(name="Timer id (see /pred list_timers)", time="New game time as M:SS",
                           message="Replace all messages with this one (optional)", category="Category")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def edit_timer(self, interaction: discord.Interaction, name: str, time: str,
                         message: Optional[app_commands.Range[str, 1, 200]] = None,
                         category: Optional[str] = None):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "edit timers")
            return
        timer = self.bot.config_manager.get_server_timers(interaction.guild.id).get(name)
        if not timer:
            await interaction.response.send_message(f"Timer `{name}` not found.", ephemeral=True)
            return
        try:
            total_seconds = GameTimer.parse_time(time)
        except ValueError:
            await interaction.response.send_message("Time must look like `M:SS`, for example `5:30`.", ephemeral=True)
            return

        messages = [message] if message else timer.get('messages', ['Timer event'])
        self.bot.config_manager.update_timer(
            interaction.guild.id, name, total_seconds, messages,
            category or timer.get('category', TimerCategory.REMINDER.value),
        )
        await interaction.response.send_message(f"Timer `{name}` updated.", ephemeral=True)

    @app_commands.command(name="remove_timer", description="Delete a callout")
    async def remove_timer(self, interaction: discord.Interaction, name: str):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "remove timers")
            return
        if self.bot.config_manager.remove_timer(interaction.guild.id, name):
            await interaction.response.send_message(f"Timer `{name}` removed.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Timer `{name}` not found.", ephemeral=True)

    @app_commands.command(name="remove_timer_message", description="Delete one message from a callout")
    @app_commands.describe(timer_name="Timer id", message_index="Message number shown in /pred list_timers")
    async def remove_timer_message(self, interaction: discord.Interaction, timer_name: str,
                                   message_index: app_commands.Range[int, 0, 50]):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "edit timers")
            return
        timer = self.bot.config_manager.get_server_timers(interaction.guild.id).get(timer_name)
        if not timer:
            await interaction.response.send_message(f"Timer `{timer_name}` not found.", ephemeral=True)
            return
        messages = list(timer.get('messages', []))
        if not 0 <= message_index < len(messages):
            await interaction.response.send_message(
                f"Invalid message number. This timer has {len(messages)} message(s).", ephemeral=True
            )
            return
        removed = messages.pop(message_index)
        if not messages:
            messages = ["Timer event"]
        self.bot.config_manager.update_timer(
            interaction.guild.id, timer_name, timer['time'], messages,
            timer.get('category', TimerCategory.REMINDER.value),
        )
        await interaction.response.send_message(f"Removed from `{timer_name}`: {removed}", ephemeral=True)

    @app_commands.command(name="list_timers", description="List all callouts, optionally by category")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def list_timers(self, interaction: discord.Interaction, category: Optional[str] = None):
        timers = self.bot.config_manager.get_server_timers(interaction.guild.id, category)
        if not timers:
            await interaction.response.send_message(
                "No timers found" + (f" in category `{category}`" if category else "") + ".", ephemeral=True
            )
            return

        sorted_timers = sorted(timers.items(), key=lambda kv: kv[1].get('time', 0))
        chunk_size = 20
        embeds = []
        for i in range(0, len(sorted_timers), chunk_size):
            chunk = sorted_timers[i:i + chunk_size]
            embed = discord.Embed(
                title=f"Callouts ({i // chunk_size + 1}/{(len(sorted_timers) - 1) // chunk_size + 1})",
                description=f"Category: `{category}`" if category else None,
                color=discord.Color.blue(),
            )
            for name, timer in chunk:
                messages = timer.get('messages', ['No message'])
                text = '\n'.join(f"{idx}. {msg}" for idx, msg in enumerate(messages))
                embed.add_field(
                    name=f"{GameTimer.format_time(timer.get('time', 0))} · {name}",
                    value=f"*{timer.get('category', 'uncategorized')}*\n{text}"[:1024],
                    inline=False,
                )
            embeds.append(embed)

        await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        for embed in embeds[1:]:
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ============================================================ import / export
    @app_commands.command(name="export_config", description="Download this server's settings and timers as JSON")
    async def export_config(self, interaction: discord.Interaction):
        try:
            config = self.bot.config_manager.get_server_config(interaction.guild.id)
            data = io.BytesIO(json.dumps(config, indent=2).encode('utf-8'))
            tts = config['settings'].get('tts_settings', {})
            embed = discord.Embed(
                title="Configuration export",
                description=(f"• {len(config.get('timers', {}))} timers\n"
                             f"• Voice: {tts.get('voice_name', DEFAULT_VOICE)}\n"
                             f"• Speed: {tts.get('speed', DEFAULT_SPEED)}x"),
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(
                embed=embed,
                file=discord.File(data, filename=f"lane_guardian_{interaction.guild.id}.json"),
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            await interaction.response.send_message("Error exporting configuration.", ephemeral=True)

    @app_commands.command(name="import_config", description="Import settings and timers from a JSON file")
    @app_commands.describe(
        file="A JSON file from /pred export_config",
        merge="Merge into the current configuration instead of replacing it",
        keep_existing_timers="When merging, keep timers that aren't in the file",
    )
    async def import_config(self, interaction: discord.Interaction, file: discord.Attachment,
                            merge: bool = True, keep_existing_timers: bool = True):
        if not await self.check_permissions(interaction):
            await self._deny(interaction, "import configurations")
            return
        if file.size > 1024 * 1024:
            await interaction.response.send_message("File too large (max 1 MB).", ephemeral=True)
            return
        if not file.filename.lower().endswith('.json'):
            await interaction.response.send_message("Please upload a `.json` file.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            config_data = json.loads((await file.read()).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            await interaction.followup.send("That file isn't valid JSON.", ephemeral=True)
            return

        is_valid, error, sanitized = self.validate_config(config_data)
        if not is_valid:
            await interaction.followup.send(f"Invalid configuration: {error}", ephemeral=True)
            return

        cm = self.bot.config_manager
        if merge:
            current = cm.get_server_config(interaction.guild.id)
            if keep_existing_timers:
                sanitized['timers'] = {**current.get('timers', {}), **sanitized['timers']}
            merged_settings = {**current.get('settings', {}), **sanitized['settings']}
            # Never let an import wipe the admin lists.
            for key in ('admin_users', 'admin_roles', 'secondary_owners'):
                merged_settings[key] = sorted(set(current['settings'].get(key, [])) | set(sanitized['settings'].get(key, [])))
            sanitized = {**current, 'settings': merged_settings, 'timers': sanitized['timers']}

        cm.configs[str(interaction.guild.id)] = sanitized
        cm.save_configs()

        tts = sanitized['settings']['tts_settings']
        embed = discord.Embed(title="Configuration imported", color=discord.Color.green())
        embed.add_field(
            name="Result",
            value=(f"• {len(sanitized['timers'])} timers\n"
                   f"• Voice: {tts.get('voice_name', DEFAULT_VOICE)}\n"
                   f"• Speed: {tts.get('speed', DEFAULT_SPEED)}x · Pitch: {tts.get('pitch', DEFAULT_PITCH)}x\n"
                   f"• Volume: {round(float(sanitized['settings'].get('volume', 1.0)) * 100)}%\n"
                   + ("• Merged with existing settings" if merge else "• Replaced existing settings")),
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
