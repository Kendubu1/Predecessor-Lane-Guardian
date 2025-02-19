from enum import Enum
import json
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

# Language-Accent valid combinations
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
        'tts_settings': {
            'language': TTSLanguage.ENGLISH.value,
            'accent': TTSAccent.AMERICAN.value,
            'warning_time': 0,
            'speed': 1.0,
            'pitch': 1.0,
            'word_gap': 0.1,
            'emphasis_volume': 1.2,
            'use_phonetics': False,
            'capitalize_proper_nouns': True,
            'number_to_words': True,
            'custom_pronunciations': {
                'Fangtooth': 'Fang tooth',
                'Orb Prime': 'Orb Prime',
            }
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
            'time': 150,  # 2:30
            'messages': [
                '30 seconds until first gold and cyan buffs spawn',
                'Gold and cyan buffs spawning in 30 seconds, prepare',
                'First buffs coming online in 30, get ready'
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
            'time': 300,  # 5:00
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
        'jungle_level_check': {
            'time': 480,  # 8:00
            'messages': [
                'Jungler should be approaching level 6',
                'Check jungler level, power spike incoming',
                'Time for jungle ultimates, prepare for ganks'
            ],
            'category': TimerCategory.FARM.value
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
        'second_fang': {
            'time': 630,  # 10:30
            'messages': [
                'Time to stack Fangtooth buffs',
                'Consider securing another Fangtooth',
                'Fangtooth stack opportunity'
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
            'time': 1140,  # 20:00
            'messages': [
                'Prepare for Orb Prime soon, win vision',
                'Orb Prime approaching, secure vision control',
                'Get ready for Orb Prime, vision is crucial'
            ],
            'category': TimerCategory.OBJECTIVE.value
        },
        'empowered_river': {
            'time': 1260,  # 21:00
            'messages': [
                'River buffs now provide empowered effects',
                'River buffs are now enhanced',
                'Empowered river buffs active'
            ],
            'category': TimerCategory.LATE_GAME.value
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
    }
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
            self.configs[server_id] = DEFAULT_CONFIG.copy()
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
            self.configs[server_id] = DEFAULT_CONFIG.copy()

        current = self.configs[server_id]
        *parts, last = path.split('.')
        
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[last] = value
        self.save_configs()

    def update_timer(self, server_id: int, timer_name: str, time: int, 
                    message: str, category: str) -> None:
        """Update or create a timer for a server."""
        server_id = str(server_id)
        if server_id not in self.configs:
            self.configs[server_id] = DEFAULT_CONFIG.copy()
        
        if 'timers' not in self.configs[server_id]:
            self.configs[server_id]['timers'] = {}

        self.configs[server_id]['timers'][timer_name] = {
            'time': time,
            'message': message,
            'category': category
        }
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
    
    def get_server_timers(self, server_id: int, category: Optional[str] = None) -> Dict[str, Any]:
        """Get all timers for a server, optionally filtered by category."""
        config = self.get_server_config(server_id)
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
            self.configs[server_id] = DEFAULT_CONFIG.copy()
        
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
