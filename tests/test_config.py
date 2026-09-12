import json
from types import SimpleNamespace

from config import (
    DEFAULT_CONFIG, DEFAULT_SPEED, DEFAULT_VOICE, EDGE_TTS_VOICES, VOICE_PRESETS,
    ConfigManager, find_preset,
)


def test_defaults_use_a_known_voice():
    tts = DEFAULT_CONFIG['settings']['tts_settings']
    assert tts['voice_name'] == DEFAULT_VOICE
    assert DEFAULT_VOICE in EDGE_TTS_VOICES
    assert tts['speed'] == DEFAULT_SPEED
    assert find_preset(tts) == 'indian-female'


def test_presets_reference_known_voices_and_fit_discord_limit():
    assert len(VOICE_PRESETS) <= 25
    for name, preset in VOICE_PRESETS.items():
        assert preset['voice_name'] in EDGE_TTS_VOICES, name
        assert len(preset['description']) <= 100, name


def test_creates_config_dir_and_default_server(tmp_path):
    path = tmp_path / "nested" / "server_configs.json"
    cm = ConfigManager(str(path))
    config = cm.get_server_config(123)
    assert config['settings']['tts_settings']['voice_name'] == DEFAULT_VOICE
    assert path.exists()
    assert json.loads(path.read_text())['123']['timers']
    assert not path.with_suffix('.json.tmp').exists()


def test_migrates_legacy_single_message_timers(tmp_path):
    path = tmp_path / "server_configs.json"
    path.write_text(json.dumps({
        "1": {"settings": {}, "timers": {"a": {"time": 10, "message": "hi", "category": "buff"}}}
    }))
    cm = ConfigManager(str(path))
    config = cm.get_server_config(1)
    assert config['timers']['a']['messages'] == ['hi']
    assert config['settings']['tts_settings']['voice_name'] == DEFAULT_VOICE
    assert config['settings']['admin_users'] == []
    assert config['settings']['bot_inviter'] is None


def test_update_and_remove_timer(tmp_path):
    cm = ConfigManager(str(tmp_path / "c.json"))
    cm.update_timer(5, "custom", 90, "say this", "reminder")
    assert cm.get_server_timers(5)['custom'] == {'time': 90, 'messages': ['say this'], 'category': 'reminder'}
    assert cm.remove_timer(5, "custom")
    assert not cm.remove_timer(5, "custom")


def test_sync_discord_admins(tmp_path):
    cm = ConfigManager(str(tmp_path / "c.json"))
    admin = SimpleNamespace(id=2, name="admin", guild_permissions=SimpleNamespace(administrator=True))
    normal = SimpleNamespace(id=3, name="user", guild_permissions=SimpleNamespace(administrator=False))
    guild = SimpleNamespace(id=42, owner_id=1, members=[admin, normal])
    assert cm.sync_discord_admins(guild) == 2
    assert set(cm.get_server_config(42)['settings']['admin_users']) == {1, 2}
    assert cm.sync_discord_admins(guild) == 0
