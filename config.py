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
            'message': 'Welcome to Predecessor. Get ready for battle',
            'category': TimerCategory.EARLY_GAME.value
        },
        'early_ward_reminder': {
            'time': 120,  # 2:00
            'message': 'Place wards for vision control',
            'category': TimerCategory.REMINDER.value
        },
        'first_gold_warning': {
            'time': 150,  # 2:30
            'message': '30 seconds until first gold and cyan buffs spawn',
            'category': TimerCategory.BUFF.value
        },
        'first_river_spawn': {
            'time': 180,  # 3:00
            'message': 'First river buffs spawning now',
            'category': TimerCategory.OBJECTIVE.value
        },
        'fangtooth_spawn': {
            'time': 300,  # 5:00
            'message': 'Fangtooth is now online',
            'category': TimerCategory.OBJECTIVE.value
        },
        'river_respawn': {
            'time': 320,  # 5:20
            'message': 'New river buffs spawning soon',
            'category': TimerCategory.BUFF.value
        },
        
        # Mid Game Phase (5:00 - 20:00)
        'vision_control': {
            'time': 400,  # 6:40
            'message': 'Support: Time to upgrade wards for better vision',
            'category': TimerCategory.REMINDER.value
        },
        'mini_prime': {
            'time': 420,  # 7:00
            'message': 'Mini Prime is available, prepare for objective',
            'category': TimerCategory.OBJECTIVE.value
        },
        'jungle_level_check': {
            'time': 480,  # 8:00
            'message': 'Jungler should be approaching level 6',
            'category': TimerCategory.FARM.value
        },
        'lane_pressure': {
            'time': 600,  # 10:00
            'message': 'Apply pressure for tower damage',
            'category': TimerCategory.OBJECTIVE.value
        },
        'carry_farm_check': {
            'time': 600,  # 10:00
            'message': 'Carry, maintain farm priority',
            'category': TimerCategory.FARM.value
        },
        'second_fang': {
            'time': 630,  # 10:30
            'message': 'Time to stack Fangtooth buffs',
            'category': TimerCategory.OBJECTIVE.value
        },
        'solo_lane_power': {
            'time': 720,  # 12:00
            'message': 'Solo lanes hitting level 9 power spike',
            'category': TimerCategory.OBJECTIVE.value
        },
        'tower_status': {
            'time': 840,  # 14:00
            'message': 'Check outer towers status, rotate if needed',
            'category': TimerCategory.OBJECTIVE.value
        },
        'orb_reminder': {
            'time': 840,  # 14:00
            'message': 'Mini Orb expiring soon',
            'category': TimerCategory.OBJECTIVE.value
        },
        'midgame_ward': {
            'time': 900,  # 15:00
            'message': 'Half way mark, maintain map control',
            'category': TimerCategory.REMINDER.value
        },
        'wave_management': {
            'time': 1020,  # 17:00
            'message': 'Push waves before taking objectives',
            'category': TimerCategory.FARM.value
        },
        
        # Late Game Phase (20:00+)
        'orb_prime_spawn': {
            'time': 1140,  # 20:00
            'message': 'Prepare for Orb Prime soon, win vision',
            'category': TimerCategory.OBJECTIVE.value
        },
        'empowered_river': {
            'time': 1260,  # 21:00
            'message': 'River buffs now provide empowered effects',
            'category': TimerCategory.LATE_GAME.value
        },
        'late_game_start': {
            'time': 1500,  # 25:00
            'message': 'Late game phase, focus on inhibitors',
            'category': TimerCategory.OBJECTIVE.value
        },
        'victory_condition': {
            'time': 1800,  # 30:00
            'message': 'Orb Prime is crucial for victory, No solo deaths',
            'category': TimerCategory.LATE_GAME.value
        },
        'deep_vision': {
            'time': 1980,  # 33:00
            'message': 'Maintain deep vision control',
            'category': TimerCategory.OBJECTIVE.value
        },
        'critical_phase': {
            'time': 2100,  # 35:00
            'message': 'Critical phase, play carefully, keep vision',
            'category': TimerCategory.LATE_GAME.value
        },
        'decisive_fight': {
            'time': 2280,  # 38:00
            'message': 'Next fight could decide the game',
            'category': TimerCategory.LATE_GAME.value
        },
        'final_push': {
            'time': 2400,  # 40:00
            'message': 'Secure objectives and end the game',
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