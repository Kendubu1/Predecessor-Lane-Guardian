import os
import logging
import gtts
import discord
import asyncio
from typing import Dict, Any
import asyncio
import tempfile
from pathlib import Path

logger = logging.getLogger('PredTimer.Services')

class TTSService:
    """Handles Text-to-Speech generation and management."""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "predtimer_tts"
        self.temp_dir.mkdir(exist_ok=True)
        logger.info("TTSService initialized")

    def create_tts_message(self, message: str, settings: Dict[str, Any]) -> str:
        """Create a TTS audio file from the given message."""
        try:
            tts_settings = settings.get('tts_settings', {})
            
            # Pre-process message based on settings
            processed_message = self._process_message(message, tts_settings)
            
            # Create TTS without speed modification (we'll handle that in FFmpeg)
            tts = gtts.gTTS(
                text=processed_message,
                lang=tts_settings.get('language', 'en'),
                tld=tts_settings.get('accent', 'co.in'),
                slow=False  # Always use normal speed, we'll adjust with FFmpeg
            )
            
            # Generate unique filename
            filename = self.temp_dir / f"temp_{hash(processed_message)}_{tts_settings.get('accent', 'co.in')}.mp3"
            tts.save(str(filename))
            
            logger.debug(f"Created TTS file: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.error(f"Error creating TTS message: {e}")
            raise

    def _process_message(self, message: str, settings: Dict[str, Any]) -> str:
        """Process message according to TTS settings."""
        # Convert numbers to words if enabled
        if settings.get('number_to_words', True):
            message = self._convert_numbers_to_words(message)
        
        # Apply custom pronunciations
        replacements = settings.get('custom_pronunciations', {})
        for old, new in replacements.items():
            message = message.replace(old, new)
        
        # Add emphasis for important words if enabled
        if settings.get('emphasis_volume', 1.2) > 1.0:
            message = self._add_emphasis(message)
        
        return message

    def _convert_numbers_to_words(self, text: str) -> str:
        """Convert numerical values to words in the text."""
        import re
        
        def num_to_words(match):
            num = int(match.group())
            units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
            teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
            tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
            
            if num < 10:
                return units[num]
            elif num < 20:
                return teens[num-10]
            elif num < 100:
                unit = num % 10
                ten = num // 10
                return tens[ten] + ("-" + units[unit] if unit else "")
            return str(num)
        
        return re.sub(r'\b\d+\b', num_to_words, text)

    def _add_emphasis(self, text: str) -> str:
        """Add emphasis markers to important words."""
        emphasis_words = {'warning', 'alert', 'danger', 'important', 'critical', 'urgent'}
        words = text.split()
        
        for i, word in enumerate(words):
            if word.lower() in emphasis_words:
                words[i] = f"<emphasis level='strong'>{word}</emphasis>"
        
        return ' '.join(words)

    def cleanup(self) -> None:
        """Clean up temporary TTS files."""
        try:
            for file in self.temp_dir.glob("temp_*.mp3"):
                try:
                    file.unlink()
                except Exception as e:
                    logger.error(f"Error deleting file {file}: {e}")
            try:
                self.temp_dir.rmdir()
            except Exception as e:
                logger.error(f"Error removing temp directory: {e}")
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")


class VoiceService:
    """Handles voice channel interactions and audio playback."""
    
    def __init__(self):
        self.tts_service = TTSService()
        logger.info("VoiceService initialized")

    async def ensure_voice_client(self, 
                                channel: discord.VoiceChannel, 
                                force_new: bool = False) -> discord.VoiceClient:
        """Ensure we have a valid voice client for the channel."""
        try:
            # Get existing voice client for the guild
            voice_client = channel.guild.voice_client
            
            if voice_client:
                # If we're already in the right channel, return the client
                if voice_client.channel.id == channel.id and not force_new:
                    return voice_client
                    
                # Otherwise, disconnect from the current channel
                await voice_client.disconnect(force=True)
            
            # Connect to the new channel
            return await channel.connect()
            
        except Exception as e:
            logger.error(f"Error ensuring voice client: {e}")
            raise

class VoiceService:
    """Handles voice channel interactions and audio playback."""
    
    def __init__(self):
        self.tts_service = TTSService()
        logger.info("VoiceService initialized")

    async def ensure_voice_client(self, 
                                channel: discord.VoiceChannel, 
                                force_new: bool = False) -> discord.VoiceClient:
        """Ensure we have a valid voice client for the channel."""
        try:
            # Get existing voice client for the guild
            voice_client = channel.guild.voice_client
            
            if voice_client:
                # If we're already in the right channel, return the client
                if voice_client.channel.id == channel.id and not force_new:
                    return voice_client
                    
                # Otherwise, disconnect from the current channel
                await voice_client.disconnect(force=True)
            
            # Connect to the new channel
            return await channel.connect()
            
        except Exception as e:
            logger.error(f"Error ensuring voice client: {e}")
            raise

    async def play_announcement(self, 
                              voice_client: discord.VoiceClient,
                              message: str,
                              settings: Dict[str, Any]) -> None:
        """Play a TTS announcement in a voice channel."""
        try:
            if voice_client.is_playing():
                voice_client.stop()

            # Create TTS file
            filename = self.tts_service.create_tts_message(message, settings)
            
            # Get volume and speed settings
            volume = settings.get('volume', 1.0)
            speed = settings.get('tts_settings', {}).get('speed', 1.0)
            
            # Build FFmpeg options with speed adjustment
            ffmpeg_options = {
                'options': f'-vn -af "atempo={speed},volume={volume}"'
            }
            
            logger.info(f"Playing audio with options: {ffmpeg_options}")
            logger.info(f"Speed setting: {speed}")
            logger.info(f"Volume setting: {volume}")
            
            # Create the FFmpeg audio source with options
            try:
                audio_source = discord.FFmpegPCMAudio(
                    filename,
                    **ffmpeg_options
                )
                logger.info("FFmpeg audio source created successfully")
            except Exception as e:
                logger.error(f"Error creating FFmpeg audio source: {e}")
                raise
            
            # Apply volume transformer
            audio_source = discord.PCMVolumeTransformer(audio_source)
            
            # Play the audio
            voice_client.play(audio_source)
            
            # Wait for audio to finish
            base_wait_time = 5
            adjusted_wait_time = base_wait_time / float(speed)
            logger.info(f"Waiting for {adjusted_wait_time} seconds for audio to complete")
            await asyncio.sleep(adjusted_wait_time)
            
            # Cleanup
            try:
                os.remove(filename)
                logger.info(f"Cleaned up temp file: {filename}")
            except Exception as e:
                logger.error(f"Error removing audio file {filename}: {e}")
            
        except Exception as e:
            logger.error(f"Error playing announcement: {e}")
            raise

    async def cleanup_voice_clients(self, guild: discord.Guild) -> None:
        """Clean up voice clients for a guild."""
        try:
            voice_client = guild.voice_client
            if voice_client:
                if voice_client.is_playing():
                    voice_client.stop()
                await voice_client.disconnect(force=True)
        except Exception as e:
            logger.error(f"Error cleaning up voice clients: {e}")
            raise

    async def cleanup_voice_clients(self, guild: discord.Guild) -> None:
        """Clean up voice clients for a guild."""
        try:
            voice_client = guild.voice_client
            if voice_client:
                if voice_client.is_playing():
                    voice_client.stop()
                await voice_client.disconnect(force=True)
        except Exception as e:
            logger.error(f"Error cleaning up voice clients: {e}")
            raise