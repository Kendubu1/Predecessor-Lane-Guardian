# Timer System Improvements - Competitive Gaming Focus

## Problem Statement

**Current Issues:**
1. ❌ Nitro mode has no timers (empty config)
2. ❌ No ARAM mode support
3. ❌ Manual `/pred start time="0:00" mode="standard"` is slow
4. ❌ No way to track objective respawns without mid-game commands
5. ❌ Timer updates require code changes and bot restart

**Goal:** Zero mid-game interaction, fast game start, automatic respawn prediction

---

## Solution 1: Ultra-Fast Game Start 🚀

### **Current:**
```
/pred start time="0:00" mode="standard"
```
- 4 words to type
- Easy to typo "standard" vs "nitro"
- Requires time parameter

### **Proposed - Quick Commands:**

```python
# Ultra-short aliases:
/go              # Start ranked/casual at 0:00
/go nitro        # Start nitro at 0:00
/go aram         # Start ARAM at 0:00
/go 2:15         # Start ranked at 2:15 (late join)

# With autocomplete:
/game quick ranked
/game quick nitro
/game quick aram
```

### **Implementation:**

```python
@app_commands.command(name="go")
async def quick_start(self, interaction: discord.Interaction,
                      mode: Optional[str] = "ranked",
                      time: Optional[str] = "0:00"):
    """Quick start game timer (shorthand for /pred start)"""
    # Same as /pred start but with better defaults
```

---

## Solution 2: React-to-Start System 🎮

### **How it works:**

```python
/game prep ranked    # Bot sends embed with ▶️ button

# Bot posts:
┌─────────────────────────────────┐
│  🎮 Predecessor Ranked Game     │
│                                 │
│  Ready to start?                │
│  React with ▶️ to begin timer  │
│                                 │
│  ▶️  [0 reactions]              │
└─────────────────────────────────┘

# Anyone reacts → Timer starts instantly
# Bot updates message:
┌─────────────────────────────────┐
│  ✅ Timer Started!              │
│  Mode: Ranked                   │
│  Started by: @PlayerName        │
│  Game Time: 0:00                │
└─────────────────────────────────┘
```

### **Benefits:**
- ✅ One-click start (even on mobile)
- ✅ Perfect for scheduled scrims
- ✅ Visual confirmation
- ✅ Shows who started (accountability)

---

## Solution 3: Voice Channel Auto-Detect 🎙️

### **Smart Start:**

```python
# Bot monitors voice channel:
# When 5+ players join → Bot sends message:

"5 players in voice! Game starting soon?"
[▶️ Start Now] [⏰ Start in 30s] [❌ Not yet]

# Click "Start in 30s":
"30 seconds to game start..."
"20 seconds..."
"10 seconds..."
"Game starting NOW!" → Timer starts
```

### **Configuration:**

```python
/game autodetect enable       # Enable auto-detection
/game autodetect channel <vc> # Set which voice channel
/game autodetect players 5    # Minimum players needed
```

### **Benefits:**
- ✅ Zero commands once configured
- ✅ Great for organized teams
- ✅ Countdown builds hype

---

## Solution 4: Smart Respawn Windows (NO COMMANDS)

Instead of manual tracking, use **statistical prediction**:

### **Current Problem:**
```
4:00 - "Fangtooth spawns"
[Player needs to type: /track fangtooth]
9:00 - "Fangtooth respawns"
```

### **New Approach - Respawn Windows:**

```python
# Assume objectives are contested within 30-60s of spawn
# Announce WINDOWS instead of exact times:

3:30  - "Fangtooth spawns in 30s - GET VISION NOW"
4:00  - "Fangtooth is UP - Contest for map control"
        "If secured, respawns at 9:00"

# Smart respawn window:
8:30  - "Fangtooth respawn window opening"
        "It respawns 5 minutes after kill"
        "If killed at spawn (4:00), it's up at 9:00"

9:00  - "Fangtooth should be spawning NOW"
        "Check minimap - contest or track enemy"

9:30  - "Late respawn window - if Fang was delayed earlier"

# This covers 4:00-4:30 kill → 9:00-9:30 respawn
# NO COMMANDS NEEDED!
```

### **Smart Announcements:**

```python
# Context-aware callouts:

7:00  - "First Fangtooth typically secured by now"
        "Check gold diff to see who has advantage"

7:30  - "Prepare for second Fangtooth window at 9:00"
        "Start getting vision control in jungle"

11:30 - "Third Fangtooth window - Stacks are critical"
        "Team with 3 stacks gets significant advantage"
```

### **Orb Prime Tracking:**

```python
# Orb Prime has buff duration - track that:

19:00 - "Orb Prime spawning NOW - Fight for vision"

19:30 - "If Orb was secured, buff lasts 3 minutes"
        "Buff expires around 22:30"

22:00 - "Orb Prime buff expiring soon"
        "Enemy push window closing"

22:30 - "Orb buff should be expired"
        "Safe to contest next spawn at 24:00"

24:00 - "Orb Prime respawn (5min after previous)"
```

---

## Solution 5: Multi-Mode Timer System

### **Current Structure:**
```python
# config.py - HARDCODED
'timers': { /* 30 ranked timers */ },
'nitro_timers': {}  # EMPTY!
```

### **Proposed Structure:**

```
timers/
├── ranked.json       # Ranked/Casual timers
├── nitro.json        # Nitro mode (faster pace)
├── aram.json         # ARAM (completely different)
└── custom/
    └── scrim_mode.json  # Team-specific custom timers
```

### **ranked.json (Current Timers):**
```json
{
  "fangtooth_spawn": {
    "time": 240,
    "messages": [
      "Fangtooth is now online",
      "Fangtooth has entered the arena"
    ],
    "category": "objective",
    "respawn_time": 300,
    "respawn_window": 30
  },
  "orb_prime_spawn": {
    "time": 1140,
    "messages": ["Orb Prime spawning NOW - Contest!"],
    "category": "objective",
    "respawn_time": 300,
    "buff_duration": 180
  }
}
```

### **nitro.json (Faster Timings):**
```json
{
  "jungle_spawn": {
    "time": 45,
    "messages": ["Jungle camps up! NITRO PACE!"],
    "category": "buff"
  },
  "fangtooth_spawn": {
    "time": 180,
    "messages": ["Fangtooth spawning FAST - Nitro mode!"],
    "category": "objective",
    "respawn_time": 240
  },
  "orb_prime_spawn": {
    "time": 900,
    "messages": ["Orb Prime - Earlier in Nitro!"],
    "category": "objective"
  }
}
```

### **aram.json (Single Lane):**
```json
{
  "game_start": {
    "time": 0,
    "messages": ["ARAM mode - Constant teamfights!"],
    "category": "early_game"
  },
  "first_teamfight": {
    "time": 180,
    "messages": ["Primary teamfight window opening"],
    "category": "objective"
  },
  "relic_spawn": {
    "time": 420,
    "messages": ["ARAM relic spawning - Contest!"],
    "category": "objective"
  }
}
```

### **Loading System:**

```python
# In config.py:
class ConfigManager:
    def load_mode_timers(self, mode: str) -> dict:
        """Load timer set for game mode"""
        timer_file = f"timers/{mode}.json"

        if not os.path.exists(timer_file):
            logger.warning(f"No timer file for {mode}, using ranked")
            timer_file = "timers/ranked.json"

        with open(timer_file) as f:
            return json.load(f)

    def hot_reload_timers(self, guild_id: int, mode: str):
        """Reload timers without restarting bot"""
        timers = self.load_mode_timers(mode)
        # Update active config
        self.configs[str(guild_id)]['active_timers'] = timers
```

### **Benefits:**
- ✅ Easy to update timers (edit JSON, no code changes)
- ✅ Hot-reload without bot restart
- ✅ Team-specific custom modes
- ✅ Version control timer changes
- ✅ Share timer configs between teams

---

## Solution 6: Timer Categories Control

### **Competitive Use Case:**

During **scrims**, teams want:
- ✅ Objective timers (Fangtooth, Orb Prime)
- ✅ Power spike warnings (Tower plating, Level 6)
- ❌ Farm reminders (too noisy)
- ❌ General tips (too distracting)

### **Category Toggle:**

```python
/timer mute farm              # Mute farm check reminders
/timer mute reminder          # Mute general reminders
/timer unmute objective       # Enable objective callouts
/timer volume objective 100   # Objectives at full volume
/timer volume reminder 30     # Reminders quieter
```

### **Presets:**

```python
/timer preset tournament
# Enables:
#   - Objectives only (Fang, Orb, River, Tower)
#   - Power spikes (Level 6, Tower plating)
# Disables:
#   - Farm reminders
#   - General tips
#   - Vision reminders (team decides this)

/timer preset practice
# Enables everything:
#   - All objectives
#   - All farm reminders
#   - All vision checks
#   - All coaching tips

/timer preset scrimmage
# Balanced:
#   - Objectives
#   - Critical power spikes
#   - Important vision timers
#   - Reduced farm/tip spam
```

---

## Implementation Priority

### **Phase 1: Critical (Do Now)** 🔴

1. **Create Nitro timer set** - File-based system
2. **Add quick start** - `/go [mode]` command
3. **Smart respawn windows** - No mid-game commands needed

### **Phase 2: High Priority** 🟡

4. **React-to-start system** - Button-based start
5. **ARAM timer set** - New game mode
6. **Category muting** - `/timer mute <category>`

### **Phase 3: Nice to Have** 🟢

7. **Voice auto-detect** - Auto-start on voice join
8. **Timer presets** - Tournament/Practice/Scrimmage modes
9. **Custom timer creation** - Teams can make their own

---

## Nitro Mode Timers - Research Needed

**Question:** What are the exact timing differences in Nitro mode?

**Knowns:**
- ✅ Faster game pace
- ✅ Earlier objective spawns
- ✅ Quicker progression

**Need to research:**
- ❓ Jungle spawn: 45s instead of 60s?
- ❓ Fangtooth: 3:00 instead of 4:00?
- ❓ Orb Prime: 15:00 instead of 19:00?
- ❓ Tower plating: 10:00 instead of 12:00?
- ❓ Gateway unlock: 6:00 instead of 8:00?

**Action:** Play test Nitro games and document exact timings.

---

## ARAM Mode Timers - Need Design

**Question:** What does ARAM even track?

ARAM is single-lane constant teamfight mode. Traditional timers don't apply.

**Possible ARAM callouts:**
- Death timers (very important in ARAM)
- Teamfight windows
- Health relic spawns
- Power spike levels (earlier in ARAM)
- Passive gold accumulation warnings

**Action:** Design ARAM-specific callout system.

---

## Next Steps

1. **TTS Upgrade:** Test Edge-TTS vs gTTS (see TTS_COMPARISON.md)
2. **Create `/go` command:** Quick start implementation
3. **Build Nitro timer set:** Research + JSON file
4. **Smart respawn windows:** No mid-game commands
5. **File-based timer system:** Easy updates

**Want me to implement Phase 1 now?**
