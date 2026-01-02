# TTS Engine Comparison for Competitive Gaming

## Current Setup: gTTS (Google Text-to-Speech)

**Pros:**
- Free
- Simple API
- Reliable

**Cons:**
- Robotic, unnatural voice
- Requires internet
- No voice customization
- Slow for real-time announcements
- Rate limits

---

## Recommended: Edge-TTS (Microsoft Neural Voices)

**Pros:**
- ⭐ **BEST QUALITY** - Neural voices sound human
- ⚡ **FAST** - Streaming API
- 🎮 **Perfect for esports** - Can sound like a caster
- 🆓 **FREE** - Unofficial but stable
- 🎵 **400+ voices** - Multiple accents, styles
- 📊 **Adjustable** - Speed, pitch, emphasis

**Cons:**
- Requires internet
- Unofficial API (but very stable)

### Voice Options for Gaming:

| Voice Name | Style | Best For |
|------------|-------|----------|
| `en-US-GuyNeural` | Deep, authoritative | Main announcer (like LCS caster) |
| `en-US-DavisNeural` | Energetic, young | Hype moments |
| `en-GB-RyanNeural` | British, clear | Professional tone |
| `en-US-JennyNeural` | Clear female | Alternative voice |
| `en-AU-WilliamNeural` | Australian, relaxed | Casual scrims |

### Example Usage:

```python
import edge_tts
import asyncio

async def announce(text: str, voice: str = "en-US-GuyNeural"):
    """Generate TTS with Edge-TTS"""
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="+10%",  # Slightly faster for urgency
        volume="+0%"
    )
    await communicate.save("announcement.mp3")

# Usage:
await announce("Fangtooth spawning in thirty seconds. Get vision control now.")
```

### Advanced Features:

```python
# Emphasis and emotion:
text = """
<speak>
    <emphasis level="strong">FANGTOOTH SPAWNING!</emphasis>
    Get vision <emphasis level="moderate">now</emphasis>.
</speak>
"""

# Prosody (speed/pitch per phrase):
text = """
<speak>
    <prosody rate="slow">Orb Prime approaching.</prosody>
    <prosody rate="fast" pitch="+10%">Thirty seconds! Move now!</prosody>
</speak>
"""
```

---

## Alternative: Piper TTS (Local/Offline)

**Pros:**
- 🔒 **OFFLINE** - No internet needed
- ⚡ **VERY FAST** - Local processing
- 🎵 **Good quality** - Neural voices
- 🆓 **FREE & OPEN SOURCE**
- 🔐 **PRIVACY** - No data sent anywhere

**Cons:**
- Initial model download (~50-200MB per voice)
- Fewer voices than Edge-TTS
- Lower quality than Edge-TTS neural voices

### Best Piper Voices for Gaming:

- `en_US-libritts-high` - High quality American English
- `en_GB-alan-medium` - British male voice
- `en_US-lessac-medium` - Female American voice

---

## Performance Comparison

| Engine | Quality | Speed | Internet | Setup |
|--------|---------|-------|----------|-------|
| **gTTS** (current) | ⭐⭐ | Slow | Required | Easy |
| **Edge-TTS** ⭐ | ⭐⭐⭐⭐⭐ | Fast | Required | Easy |
| **Piper TTS** | ⭐⭐⭐⭐ | Very Fast | Not needed | Medium |
| **Coqui TTS** | ⭐⭐⭐⭐ | Slow | Not needed | Hard |

---

## Recommendation

**For Competitive Gaming:** Use **Edge-TTS with en-US-GuyNeural**

**Why:**
1. Sounds professional (like LCS/LEC casters)
2. Fast enough for real-time callouts
3. Free and reliable
4. Can customize voice per team preference
5. Easy to implement (drop-in replacement)

**Implementation:** See `services.py` for integration example.

---

## Audio Samples (Test These)

Generate test audio files:

```bash
# Install Edge-TTS
pip install edge-tts

# Test voices:
edge-tts --voice en-US-GuyNeural --text "Fangtooth spawning in thirty seconds" --write-media test_guy.mp3
edge-tts --voice en-US-DavisNeural --text "Orb Prime is up! Contest now!" --write-media test_davis.mp3
edge-tts --voice en-GB-RyanNeural --text "Tower plating falls in ten seconds" --write-media test_ryan.mp3

# Compare with current gTTS
gtts-cli "Fangtooth spawning in thirty seconds" --output test_gtts.mp3
```

Listen to each and decide which sounds best for your team!

---

## Future: Custom Voice Training

Using Coqui TTS, you could:
- Train a voice model on pro player commentary
- Create a custom "team announcer" voice
- Clone your coach's voice for callouts
- Add personality to the bot

This is advanced but possible for teams that want a unique identity.
