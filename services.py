"""Text-to-speech generation and Discord voice playback."""
import asyncio
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import discord
import edge_tts

logger = logging.getLogger('PredTimer.Services')

DEFAULT_VOICE = 'en-IN-NeerjaNeural'


class TTSService:
    """Generates speech audio files with Edge-TTS (Microsoft neural voices)."""

    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "predtimer_tts"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info("TTSService initialized with Edge-TTS")

    async def create_tts_message(self, message: str, settings: Dict[str, Any]) -> str:
        """Create a TTS audio file from the given message and return its path."""
        tts_settings = settings.get('tts_settings', {})
        processed_message = self._process_message(message, tts_settings)

        voice_name = tts_settings.get('voice_name') or DEFAULT_VOICE
        rate = self._get_rate_string(float(tts_settings.get('speed', 1.0)))
        pitch = self._get_pitch_string(float(tts_settings.get('pitch', 1.0)))

        # Unique per call so concurrent announcements never share a file.
        filename = self.temp_dir / f"tts_{uuid.uuid4().hex}.mp3"

        try:
            communicate = edge_tts.Communicate(
                text=processed_message,
                voice=voice_name,
                rate=rate,
                pitch=pitch,
            )
            await communicate.save(str(filename))
        except Exception as e:
            logger.error(f"Error creating Edge-TTS message ({voice_name}): {e}")
            filename.unlink(missing_ok=True)
            raise

        logger.debug(f"Created Edge-TTS file {filename} with voice {voice_name}")
        return str(filename)

    @staticmethod
    def _get_rate_string(speed: float) -> str:
        """Convert a speed multiplier (1.0 = normal) to an Edge-TTS rate string."""
        percentage = int(round((speed - 1.0) * 100))
        return f"{percentage:+d}%"

    @staticmethod
    def _get_pitch_string(pitch: float) -> str:
        """Convert a pitch multiplier (1.0 = normal) to an Edge-TTS pitch string."""
        hz = int(round((pitch - 1.0) * 100))
        return f"{hz:+d}Hz"

    def _process_message(self, message: str, settings: Dict[str, Any]) -> str:
        """Apply per-server text tweaks before synthesis."""
        if settings.get('number_to_words', True):
            message = self._convert_numbers_to_words(message)

        for old, new in settings.get('custom_pronunciations', {}).items():
            if old:
                message = message.replace(old, new)

        return message

    @staticmethod
    def _convert_numbers_to_words(text: str) -> str:
        """Spell out integers below 100 so the voice reads them naturally."""
        units = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
                 "sixteen", "seventeen", "eighteen", "nineteen"]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

        def num_to_words(match: re.Match) -> str:
            num = int(match.group())
            if num < 10:
                return units[num]
            if num < 20:
                return teens[num - 10]
            if num < 100:
                unit = num % 10
                return tens[num // 10] + (f"-{units[unit]}" if unit else "")
            return str(num)

        return re.sub(r'\b\d+\b', num_to_words, text)

    def cleanup(self) -> None:
        """Delete any leftover temp audio files."""
        for file in self.temp_dir.glob("tts_*.mp3"):
            try:
                file.unlink()
            except OSError as e:
                logger.error(f"Error deleting file {file}: {e}")


class VoiceService:
    """Manages voice channel connections and serialized audio playback per guild."""

    # Upper bound on how long a single announcement may play before we move on.
    MAX_PLAYBACK_SECONDS = 60.0

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.tts_service = TTSService()
        self.voice_timeouts: Dict[int, asyncio.Task] = {}
        self.INACTIVITY_TIMEOUT = int(os.getenv('VOICE_INACTIVITY_TIMEOUT', '300'))
        self._playback_locks: Dict[int, asyncio.Lock] = {}
        logger.info("VoiceService initialized")

    # ------------------------------------------------------------------ helpers
    def _lock_for(self, guild_id: int) -> asyncio.Lock:
        lock = self._playback_locks.get(guild_id)
        if lock is None:
            lock = self._playback_locks[guild_id] = asyncio.Lock()
        return lock

    def _timer_active(self, guild_id: int) -> bool:
        get_timer = getattr(self.bot, 'get_timer', None)
        if get_timer is None:
            return False
        timer = get_timer(guild_id, create=False)
        return bool(timer and timer.is_active)

    # --------------------------------------------------------- inactivity timer
    async def reset_inactivity_timer(self, voice_client: discord.VoiceClient) -> None:
        """Restart the idle countdown for this guild's voice connection."""
        guild_id = voice_client.guild.id
        existing = self.voice_timeouts.get(guild_id)
        if existing:
            existing.cancel()
        self.voice_timeouts[guild_id] = asyncio.create_task(self._inactivity_timeout(voice_client))

    async def _inactivity_timeout(self, voice_client: discord.VoiceClient) -> None:
        """Leave the channel after INACTIVITY_TIMEOUT seconds if no timer is running."""
        try:
            await asyncio.sleep(self.INACTIVITY_TIMEOUT)
            if voice_client.is_connected() and not self._timer_active(voice_client.guild.id):
                logger.info(
                    f"Leaving voice in guild {voice_client.guild.id} after "
                    f"{self.INACTIVITY_TIMEOUT}s of inactivity"
                )
                await self.cleanup_voice_clients(voice_client.guild)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in inactivity timeout: {e}")

    # ---------------------------------------------------------------- connect
    async def ensure_voice_client(self,
                                  channel: discord.VoiceChannel,
                                  timeout: float = 20.0) -> discord.VoiceClient:
        """Return a connected voice client for `channel`, joining or moving as needed."""
        guild = channel.guild
        voice_client = guild.voice_client

        if voice_client is not None:
            if voice_client.is_connected():
                if voice_client.channel.id != channel.id:
                    logger.info(f"Moving voice client in guild {guild.id} to channel {channel.id}")
                    await voice_client.move_to(channel)
                await self.reset_inactivity_timer(voice_client)
                return voice_client
            # Stale client left over from a dropped connection; clear it first.
            logger.warning(f"Discarding stale voice client in guild {guild.id}")
            await voice_client.disconnect(force=True)

        try:
            voice_client = await channel.connect(timeout=timeout, reconnect=True, self_deaf=True)
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to voice channel {channel.id} in guild {guild.id}")
            raise
        except discord.ClientException as e:
            # "Already connected" race: reuse whatever discord.py has.
            if guild.voice_client and guild.voice_client.is_connected():
                voice_client = guild.voice_client
            else:
                logger.error(f"Error connecting to voice channel {channel.id}: {e}")
                raise

        logger.info(f"Connected to voice channel {channel.name} ({channel.id}) in guild {guild.id}")
        await self.reset_inactivity_timer(voice_client)
        return voice_client

    # ---------------------------------------------------------------- playback
    async def play_announcement(self,
                                voice_client: discord.VoiceClient,
                                message: str,
                                settings: Dict[str, Any]) -> None:
        """Speak `message` in the voice channel, waiting for playback to finish.

        Announcements for the same guild are serialized so two events firing at
        the same game time do not cut each other off.
        """
        guild_id = voice_client.guild.id
        async with self._lock_for(guild_id):
            if not voice_client.is_connected():
                raise discord.ClientException("Not connected to voice.")

            filename = await self.tts_service.create_tts_message(message, settings)
            try:
                volume = max(0.0, min(2.0, float(settings.get('volume', 1.0))))
                # Encode straight to Opus in ffmpeg: cheaper than PCM + Python
                # resampling, and it avoids the removed `audioop` module.
                source = discord.FFmpegOpusAudio(
                    filename,
                    options=f'-af volume={volume}',
                )

                loop = asyncio.get_running_loop()
                finished = asyncio.Event()

                def _after(error: Optional[Exception]) -> None:
                    if error:
                        logger.error(f"Playback error in guild {guild_id}: {error}")
                    loop.call_soon_threadsafe(finished.set)

                if voice_client.is_playing():
                    voice_client.stop()

                logger.info(f"[{guild_id}] Speaking: {message!r} (volume={volume})")
                voice_client.play(source, after=_after)
                await self.reset_inactivity_timer(voice_client)

                try:
                    await asyncio.wait_for(finished.wait(), timeout=self.MAX_PLAYBACK_SECONDS)
                except asyncio.TimeoutError:
                    logger.warning(f"[{guild_id}] Announcement exceeded {self.MAX_PLAYBACK_SECONDS}s, stopping")
                    voice_client.stop()
            finally:
                try:
                    os.remove(filename)
                except OSError as e:
                    logger.debug(f"Could not remove {filename}: {e}")

    # ---------------------------------------------------------------- cleanup
    async def cleanup_voice_clients(self, guild: discord.Guild) -> None:
        """Disconnect from voice in `guild` and cancel its idle timer."""
        task = self.voice_timeouts.pop(guild.id, None)
        if task:
            task.cancel()

        voice_client = guild.voice_client
        if voice_client:
            try:
                if voice_client.is_playing():
                    voice_client.stop()
                await voice_client.disconnect(force=True)
                logger.info(f"Disconnected from voice in guild {guild.id}")
            except Exception as e:
                logger.error(f"Error disconnecting from voice in guild {guild.id}: {e}")
                raise

    def forget_guild(self, guild_id: int) -> None:
        """Drop per-guild state after the connection is gone."""
        task = self.voice_timeouts.pop(guild_id, None)
        if task:
            task.cancel()
        self._playback_locks.pop(guild_id, None)
