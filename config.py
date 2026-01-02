from enum import Enum
import json
import copy
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('PredTimer.Config')

class TimerCategory(Enum):
    EARLY_GAME = "early_game"
    MID_GAME = "mid_game"
    LATE_GAME = "late_game"
    OBJECTIVE = "objective"
    BUFF = "buff"
    FARM = "farm"
    REMINDER = "reminder"

class TTSAccent(Enum):
    # English variants
    AUSTRALIAN = "com.au"
    BRITISH = "co.uk"
    AMERICAN = "us"
    CANADIAN = "ca"
    INDIAN = "co.in"
    IRISH = "ie"
    SOUTH_AFRICAN = "co.za"
    NIGERIAN = "com.ng"
    
    # French variants
    FRENCH_CANADIAN = "ca"
    FRENCH = "fr"
    
    # Chinese variants (note: TLD doesn't affect these)
    CHINESE_MAINLAND = "com"
    CHINESE_TAIWAN = "com"
    
    # Portuguese variants
    PORTUGUESE_BRAZIL = "com.br"
    PORTUGUESE = "pt"
    
    # Spanish variants
    SPANISH_MEXICO = "com.mx"
    SPANISH = "es"
    SPANISH_US = "us"

class TTSLanguage(Enum):
    # English
    ENGLISH = "en"
    
    # French
    FRENCH = "fr"
    
    # Chinese
    CHINESE_MAINLAND = "zh-CN"
    CHINESE_TAIWAN = "zh-TW"
    
    # Portuguese
    PORTUGUESE = "pt"
    
    # Spanish
    SPANISH = "es"

class TTSSpeed(Enum):
    VERY_SLOW = 0.5
    SLOW = 0.75
    NORMAL = 1.0
    FAST = 1.25
    VERY_FAST = 1.5

# Edge-TTS Voice Options
EDGE_TTS_VOICES = {
    # Indian Voices (English)
    'en-IN-NeerjaNeural': 'Indian Female (Neerja) - Clear, Professional',
    'en-IN-PrabhatNeural': 'Indian Male (Prabhat) - Deep, Authoritative',

    # Hindi Voices
    'hi-IN-SwaraNeural': 'Hindi Female (Swara) - Natural',
    'hi-IN-MadhurNeural': 'Hindi Male (Madhur) - Clear',

    # American English (Popular for esports)
    'en-US-AriaNeural': 'American Female (Aria) - Friendly, Clear',
    'en-US-GuyNeural': 'American Male (Guy) - Deep, Caster-like',
    'en-US-JennyNeural': 'American Female (Jenny) - Professional',
    'en-US-DavisNeural': 'American Male (Davis) - Energetic, Young',

    # British English
    'en-GB-SoniaNeural': 'British Female (Sonia) - Professional',
    'en-GB-RyanNeural': 'British Male (Ryan) - Clear, Energetic',

    # Australian English
    'en-AU-NatashaNeural': 'Australian Female (Natasha) - Friendly',
    'en-AU-WilliamNeural': 'Australian Male (William) - Relaxed',
}

# Voice Presets for Easy Selection
VOICE_PRESETS = {
    # Indian Presets (Default)
    'indian-female': {
        'voice_name': 'en-IN-NeerjaNeural',
        'description': '🇮🇳 Indian Female - Clear, Professional (Neerja)',
        'speed': 1.0,
        'pitch': 1.0
    },
    'indian-male': {
        'voice_name': 'en-IN-PrabhatNeural',
        'description': '🇮🇳 Indian Male - Deep, Authoritative (Prabhat)',
        'speed': 1.0,
        'pitch': 1.0
    },

    # Hindi Presets
    'hindi-female': {
        'voice_name': 'hi-IN-SwaraNeural',
        'description': '🇮🇳 Hindi Female - Natural (Swara)',
        'speed': 1.0,
        'pitch': 1.0
    },
    'hindi-male': {
        'voice_name': 'hi-IN-MadhurNeural',
        'description': '🇮🇳 Hindi Male - Clear (Madhur)',
        'speed': 1.0,
        'pitch': 1.0
    },

    # American Esports Presets
    'esports-caster': {
        'voice_name': 'en-US-GuyNeural',
        'description': '🎮 Esports Caster - Deep, Professional (Guy)',
        'speed': 1.1,
        'pitch': 0.95
    },
    'hype-voice': {
        'voice_name': 'en-US-DavisNeural',
        'description': '🔥 Hype Voice - Energetic, Young (Davis)',
        'speed': 1.15,
        'pitch': 1.05
    },
    'american-female': {
        'voice_name': 'en-US-AriaNeural',
        'description': '🇺🇸 American Female - Friendly, Clear (Aria)',
        'speed': 1.0,
        'pitch': 1.0
    },
    'professional-female': {
        'voice_name': 'en-US-JennyNeural',
        'description': '🎙️ Professional Female - Broadcast Quality (Jenny)',
        'speed': 1.0,
        'pitch': 1.0
    },

    # British Presets
    'british-male': {
        'voice_name': 'en-GB-RyanNeural',
        'description': '🇬🇧 British Male - Clear, Energetic (Ryan)',
        'speed': 1.0,
        'pitch': 1.0
    },
    'british-female': {
        'voice_name': 'en-GB-SoniaNeural',
        'description': '🇬🇧 British Female - Professional (Sonia)',
        'speed': 1.0,
        'pitch': 1.0
    },

    # Australian Presets
    'australian-male': {
        'voice_name': 'en-AU-WilliamNeural',
        'description': '🇦🇺 Australian Male - Relaxed (William)',
        'speed': 1.0,
        'pitch': 1.0
    },
    'australian-female': {
        'voice_name': 'en-AU-NatashaNeural',
        'description': '🇦🇺 Australian Female - Friendly (Natasha)',
        'speed': 1.0,
        'pitch': 1.0
    },
}

# Language-Accent valid combinations (kept for backwards compatibility)
VALID_LANG_ACCENT_PAIRS = {
    # English combinations
    ('en', 'com.au'): "English (Australia)",
    ('en', 'co.uk'): "English (United Kingdom)",
    ('en', 'us'): "English (United States)",
    ('en', 'ca'): "English (Canada)",
    ('en', 'co.in'): "English (India)",
    ('en', 'ie'): "English (Ireland)",
    ('en', 'co.za'): "English (South Africa)",
    ('en', 'com.ng'): "English (Nigeria)",
    
    # French combinations
    ('fr', 'ca'): "French (Canada)",
    ('fr', 'fr'): "French (France)",
    
    # Chinese combinations
    ('zh-CN', 'com'): "Mandarin (China Mainland)",
    ('zh-TW', 'com'): "Mandarin (Taiwan)",
    
    # Portuguese combinations
    ('pt', 'com.br'): "Portuguese (Brazil)",
    ('pt', 'pt'): "Portuguese (Portugal)",
    
    # Spanish combinations
    ('es', 'com.mx'): "Spanish (Mexico)",
    ('es', 'es'): "Spanish (Spain)",
    ('es', 'us'): "Spanish (United States)",
}

DEFAULT_CONFIG = {
    'settings': {
        'volume': 1.0,
        'admin_roles': [],
        'admin_users': [],
        'secondary_owners': [],
        'bot_inviter': None,  # Track who invited the bot
        'tts_settings': {
            'voice_name': 'en-IN-NeerjaNeural',  # Indian female voice (Edge-TTS)
            'language': TTSLanguage.ENGLISH.value,  # Legacy (backwards compatibility)
            'accent': TTSAccent.INDIAN.value,  # Legacy (backwards compatibility)
            'speed': 1.0,
            'pitch': 1.0,
            'number_to_words': True,  # Convert "3" to "three"
            'emphasis_volume': 1.2,  # Make keywords louder (1.0-2.0)
            'custom_pronunciations': {}  # Dict of custom word replacements
        }
    },
    'timers': {
        # Early Game Phase (0:00 - 5:00)
        'game_start': {
            'time': 0,
            'messages': [
                'Welcome to Predecessor. Get ready for battle',
                'The battle begins now, good luck Predecessors',
                'Game on! May fortune favor the bold',
                'Welcome to the arena. Show them what you\'re made of'
            ],
            'category': TimerCategory.EARLY_GAME.value
        },
        'jungle_spawn': {
            'time': 60,  # 1:00 - Updated for v1.4
            'messages': [
                'Jungle camps are spawning now',
                'Red and blue buffs now available',
                'Jungle is live, secure your buffs'
            ],
            'category': TimerCategory.BUFF.value
        },
        'early_ward_reminder': {
            'time': 120,  # 2:00
            'messages': [
                'Place wards for vision control',
                'Time to secure vision, get those wards down',
                'Ward up team, protect your lanes',
                'Vision wins games, place those wards'
            ],
            'category': TimerCategory.REMINDER.value
        },
        'first_gold_warning': {
            'time': 110,  # 2:30
            'messages': [
                '10 seconds until first gold and cyan buffs spawn',
                'Gold and cyan buffs spawning in 10 seconds, prepare',
                'First buffs coming online in 10, get ready'
            ],
            'category': TimerCategory.BUFF.value
        },
        'first_river_spawn': {
            'time': 180,  # 3:00
            'messages': [
                'First river buffs spawning now',
                'River buffs are up, secure the advantage'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'fangtooth_spawn': {
            'time': 240,  # 4:00 - Updated for v1.4 (was 5:00)
            'messages': [
                'Fangtooth is now online',
                'Fangtooth has entered the arena',
                'The Fangtooth awaits challengers'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'river_respawn': {
            'time': 320,  # 5:20
            'messages': [
                'New river buffs spawning soon',
                'River buffs respawning shortly',
                'Prepare for next river buff spawn'
            ],
            'category': TimerCategory.BUFF.value
        },
        
        # Mid Game Phase (5:00 - 20:00)
        'vision_control': {
            'time': 400,  # 6:40
            'messages': [
                'Support: Time to upgrade wards for better vision',
                'Support, enhance your vision game with upgraded wards',
                'Time to boost your ward game, support'
            ],
            'category': TimerCategory.REMINDER.value
        },
        'mini_prime': {
            'time': 420,  # 7:00
            'messages': [
                'Mini Prime is available, prepare for objective',
                'Mini Prime has spawned, consider contesting',
                'Time to fight for Mini Prime control'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'gateway_spawn': {
            'time': 480,  # 8:00 - Added for v1.4 (was 10:00)
            'messages': [
                'Gateways are now active, unlock map mobility',
                'Gateways online, use them for map control',
                'Gateways available, rotate faster'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'jungle_level_check': {
            'time': 480,  # 8:00
            'messages': [
                'Jungler should be approaching level 6',
                'Check jungler level, power spike incoming',
                'Time for jungle ultimates, prepare for ganks'
            ],
            'category': TimerCategory.FARM.value
        },
        'second_fang': {
            'time': 570,  # 9:30 - Updated for v1.4 (was 10:30)
            'messages': [
                'Time to stack Fangtooth buffs',
                'Consider securing another Fangtooth',
                'Fangtooth stack opportunity'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'lane_pressure': {
            'time': 600,  # 10:00
            'messages': [
                'Apply pressure for tower damage',
                'Look for tower opportunities',
                'Time to threaten objectives'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'carry_farm_check': {
            'time': 600,  # 10:00
            'messages': [
                'Carry, maintain farm priority',
                'Carries, keep that farm up',
                'Don\'t fall behind on farm, carries'
            ],
            'category': TimerCategory.FARM.value
        },
        'tower_plating_warning': {
            'time': 690,  # 11:30 - New for v1.4
            'messages': [
                'Tower plating will fall in 30 seconds',
                '30 seconds until tower platings are removed',
                'Get last tower plating gold in 30 seconds'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'tower_plating': {
            'time': 720,  # 12:00 - New for v1.4
            'messages': [
                'Tower platings are falling, get last tower gold now',
                'Tower plating fortification ending soon',
                'Last chance for tower plating gold, push now'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'solo_lane_power': {
            'time': 720,  # 12:00
            'messages': [
                'Solo lanes hitting level 9 power spike',
                'Solo laners reaching critical level',
                'Watch for solo lane aggression'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'tower_status': {
            'time': 840,  # 14:00
            'messages': [
                'Check outer towers status, rotate if needed',
                'Time to evaluate tower positions',
                'Assess tower damage, plan rotations'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'orb_reminder': {
            'time': 840,  # 14:00
            'messages': [
                'Mini Orb expiring soon',
                'Mini Orb buff ending shortly',
                'Prepare for Mini Orb expiration'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'midgame_ward': {
            'time': 900,  # 15:00
            'messages': [
                'Half way mark, maintain map control',
                'Mid game phase, secure your vision',
                'Keep up the vision game, control the map'
            ],
            'category': TimerCategory.REMINDER.value
        },
        'empowered_river': {
            'time': 960,  # 16:00 - Updated for v1.4 (was 21:00)
            'messages': [
                'River buffs now provide empowered effects',
                'River buffs are now enhanced',
                'Empowered river buffs active'
            ],
            'category': TimerCategory.LATE_GAME.value
        },
        'wave_management': {
            'time': 1020,  # 17:00
            'messages': [
                'Push waves before taking objectives',
                'Manage those waves before objectives',
                'Clear lanes before contesting objectives'
            ],
            'category': TimerCategory.FARM.value
        },
        
        # Late Game Phase (20:00+)
        'orb_prime_spawn': {
            'time': 1140,  # 19:00
            'messages': [
                'Prepare for Orb Prime soon, win vision',
                'Orb Prime approaching, secure vision control',
                'Get ready for Orb Prime, vision is crucial'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'late_game_start': {
            'time': 1500,  # 25:00
            'messages': [
                'Late game phase, focus on inhibitors',
                'Time to crack those inhibitors',
                'Push for inhibitor advantage'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'victory_condition': {
            'time': 1800,  # 30:00
            'messages': [
                'Orb Prime is crucial for victory, No solo deaths',
                'Stay grouped, Orb Prime will decide the game',
                'One death could cost everything, stick together'
            ],
            'category': TimerCategory.LATE_GAME.value
        },
        'deep_vision': {
            'time': 1980,  # 33:00
            'messages': [
                'Maintain deep vision control',
                'Keep up aggressive vision',
                'Don\'t let vision control slip'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'critical_phase': {
            'time': 2100,  # 35:00
            'messages': [
                'Critical phase, play carefully, keep vision',
                'One mistake could end it, stay focused',
                'Maximum concentration needed now'
            ],
            'category': TimerCategory.LATE_GAME.value
        },
        'decisive_fight': {
            'time': 2280,  # 38:00
            'messages': [
                'Next fight could decide the game',
                'The next engagement is crucial',
                'Fight smart, the game hangs in the balance'
            ],
            'category': TimerCategory.LATE_GAME.value
        },
        'final_push': {
            'time': 2400,  # 40:00
            'messages': [
                'Secure objectives and end the game',
                'Time to close this out, stay focused',
                'Push for the victory, maintain discipline'
            ],
            'category': TimerCategory.LATE_GAME.value
        }
    },
    'nitro_timers': {}
}

class ConfigManager:
    """Handles server-specific configurations and settings."""
    
    def __init__(self, config_file: str = 'server_configs.json'):
        self.config_file = config_file
        self.configs = self._load_configs()
        logger.info("ConfigManager initialized")

    def _load_configs(self) -> Dict[str, Any]:
        """Load configurations from file."""
        try:
            with open(self.config_file, 'r') as f:
                configs = json.load(f)
                logger.info(f"Loaded configurations for {len(configs)} servers")
                return configs
        except FileNotFoundError:
            logger.info("No existing config file found, creating new configuration")
            return {}
        except json.JSONDecodeError:
            logger.error("Error decoding config file, creating new configuration")
            return {}

    def save_configs(self) -> None:
        """Save current configurations to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.configs, f, indent=4)

    def get_server_config(self, server_id: int) -> Dict[str, Any]:
        """Get configuration for a specific server."""
        server_id = str(server_id)
        if server_id not in self.configs:
            self.configs[server_id] = copy.deepcopy(DEFAULT_CONFIG)
            self.save_configs()
        return self.configs[server_id]
    
    def _migrate_config(self, config: dict) -> dict:
        """Migrate old config format to new format."""
        try:
            # Deep copy to avoid modifying original during migration
            migrated = json.loads(json.dumps(config))
            was_migrated = False
            
            # Migrate timers
            if 'timers' in migrated:
                for timer_name, timer in migrated['timers'].items():
                    if 'message' in timer and 'messages' not in timer:
                        # Convert single message to messages array
                        timer['messages'] = [timer.pop('message')]
                        was_migrated = True
            
            # Ensure settings structure exists
            if 'settings' not in migrated:
                migrated['settings'] = {}
                was_migrated = True
                
            if 'tts_settings' not in migrated['settings']:
                migrated['settings']['tts_settings'] = {}
                was_migrated = True
            
            tts_settings = migrated['settings']['tts_settings']
            
            # Add new TTS settings if they don't exist
            default_tts = {
                'voice_name': 'en-IN-NeerjaNeural',  # Indian female voice
                'language': 'en',  # Legacy (backwards compatibility)
                'accent': 'co.in',  # Legacy (backwards compatibility)
                'speed': 1.0,
                'pitch': 1.0,
                'number_to_words': True,  # Convert "3" to "three"
                'emphasis_volume': 1.2,  # Make keywords louder (1.0-2.0)
                'custom_pronunciations': {}  # Dict of custom word replacements
            }
            
            for key, default_value in default_tts.items():
                if key not in tts_settings:
                    tts_settings[key] = default_value
                    was_migrated = True
            
            # Ensure admin lists exist
            if 'admin_roles' not in migrated['settings']:
                migrated['settings']['admin_roles'] = []
                was_migrated = True

            if 'admin_users' not in migrated['settings']:
                migrated['settings']['admin_users'] = []
                was_migrated = True

            if 'secondary_owners' not in migrated['settings']:
                migrated['settings']['secondary_owners'] = []
                was_migrated = True

            if 'bot_inviter' not in migrated['settings']:
                migrated['settings']['bot_inviter'] = None
                was_migrated = True
                
            if was_migrated:
                logger.info("Config was migrated to new format")
                
            return migrated
        except Exception as e:
            logger.error(f"Error migrating config: {e}")
            return config  # Return original if migration fails

    def _load_configs(self) -> Dict[str, Any]:
        """Load configurations from file with migration."""
        try:
            with open(self.config_file, 'r') as f:
                configs = json.load(f)
                migrated_configs = {}
                
                # Migrate each server's config
                for server_id, config in configs.items():
                    logger.info(f"Checking config for server {server_id}")
                    migrated_configs[server_id] = self._migrate_config(config)
                
                # If any configs were migrated, save the changes
                if configs != migrated_configs:
                    logger.info("Saving migrated configurations")
                    with open(self.config_file, 'w') as f:
                        json.dump(migrated_configs, f, indent=4)
                
                logger.info(f"Loaded configurations for {len(configs)} servers")
                return migrated_configs
        except FileNotFoundError:
            logger.info("No existing config file found, creating new configuration")
            return {}
        except json.JSONDecodeError:
            logger.error("Error decoding config file, creating new configuration")
            return {}

    def update_server_setting(self, server_id: int, path: str, value: Any) -> None:
        """Update a specific setting for a server using dot notation path."""
        server_id = str(server_id)
        if server_id not in self.configs:
            self.configs[server_id] = copy.deepcopy(DEFAULT_CONFIG)

        current = self.configs[server_id]
        *parts, last = path.split('.')

        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[last] = value
        self.save_configs()

    def remove_timer(self, server_id: int, timer_name: str) -> bool:
        """Remove a timer from a server's configuration."""
        server_id = str(server_id)
        if (server_id in self.configs and 
            'timers' in self.configs[server_id] and 
            timer_name in self.configs[server_id]['timers']):
            del self.configs[server_id]['timers'][timer_name]
            self.save_configs()
            return True
        return False
    
    def get_server_timers(self, server_id: int, category: Optional[str] = None,
                          mode: str = 'standard') -> Dict[str, Any]:
        """Get timers for a server and mode, optionally filtered by category."""
        config = self.get_server_config(server_id)
        if mode == 'nitro':
            timers = config.get('nitro_timers', {})
        else:
            timers = config.get('timers', {})
        
        if category:
            return {
                name: timer for name, timer in timers.items()
                if timer.get('category') == category
            }
        return timers
    
    def _validate_timer_structure(self, timer_data: dict) -> dict:
        """Convert old timer format to new format if needed and validate structure."""
        validated = {
            'time': timer_data.get('time', 0),
            'category': timer_data.get('category', TimerCategory.REMINDER.value)
        }
        
        # Handle old format (single message) vs new format (messages array)
        if 'message' in timer_data:
            validated['messages'] = [timer_data['message']]
        elif 'messages' in timer_data:
            if isinstance(timer_data['messages'], list):
                validated['messages'] = timer_data['messages']
            else:
                validated['messages'] = [str(timer_data['messages'])]
        else:
            validated['messages'] = ['Timer event']
            
        return validated
    
    def update_timer(self, server_id: int, timer_name: str, time: int,
                messages: list[str] | str, category: str) -> None:
        """Update or create a timer for a server."""
        server_id = str(server_id)
        if server_id not in self.configs:
            self.configs[server_id] = copy.deepcopy(DEFAULT_CONFIG)

        if 'timers' not in self.configs[server_id]:
            self.configs[server_id]['timers'] = {}

        # Handle single message vs list of messages
        if isinstance(messages, str):
            messages = [messages]

        self.configs[server_id]['timers'][timer_name] = {
            'time': time,
            'messages': messages,
            'category': category
        }
        self.save_configs()

    def sync_discord_admins(self, guild) -> int:
        """
        Sync Discord administrators to bot admin list.
        Returns the number of new admins added.
        """
        server_id = str(guild.id)
        config = self.get_server_config(guild.id)
        admin_users = set(config.get('settings', {}).get('admin_users', []))
        initial_count = len(admin_users)

        # Always include server owner
        admin_users.add(guild.owner_id)

        # Add all members with Administrator permission
        for member in guild.members:
            if member.guild_permissions.administrator:
                admin_users.add(member.id)
                logger.info(f"Auto-added Discord admin: {member.name} ({member.id}) to guild {guild.id}")

        # Add secondary owners if configured
        secondary_owners = config.get('settings', {}).get('secondary_owners', [])
        for owner_id in secondary_owners:
            admin_users.add(owner_id)

        # Update config if there are changes
        new_count = len(admin_users)
        if new_count > initial_count:
            self.update_server_setting(
                guild.id,
                'settings.admin_users',
                list(admin_users)
            )
            logger.info(f"Synced {new_count - initial_count} new admin(s) for guild {guild.id}")

        return new_count - initial_count

    def add_bot_inviter(self, guild_id: int, inviter_id: int) -> None:
        """
        Record who invited the bot and grant them admin access.
        """
        server_id = str(guild_id)
        config = self.get_server_config(guild_id)

        # Record the inviter
        current_inviter = config.get('settings', {}).get('bot_inviter')
        if current_inviter is None:
            self.update_server_setting(guild_id, 'settings.bot_inviter', inviter_id)
            logger.info(f"Recorded bot inviter: {inviter_id} for guild {guild_id}")

        # Add inviter to admin users
        admin_users = set(config.get('settings', {}).get('admin_users', []))
        if inviter_id not in admin_users:
            admin_users.add(inviter_id)
            self.update_server_setting(
                guild_id,
                'settings.admin_users',
                list(admin_users)
            )
            logger.info(f"Granted admin access to bot inviter: {inviter_id} for guild {guild_id}")
