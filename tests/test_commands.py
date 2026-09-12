from types import SimpleNamespace

from commands import GameCommands
from config import DEFAULT_VOICE, TimerCategory


def make_group():
    return GameCommands(SimpleNamespace(config_manager=None, voice_service=None))


def test_group_fits_discord_subcommand_limit():
    group = make_group()
    names = {c.name for c in group.commands}
    assert len(group.commands) <= 25
    assert {'start', 'stop', 'status', 'say', 'voice_preset', 'set_tts', 'settings', 'help'} <= names


def test_validate_config_sanitizes():
    group = make_group()
    ok, err, out = group.validate_config({
        'settings': {
            'volume': 5,
            'admin_users': ['12', 'x'],
            'tts_settings': {'voice_name': 'not-a-voice', 'speed': '9', 'warning_time': 999},
        },
        'timers': {
            'good': {'time': '30', 'message': 'hi', 'category': 'nope'},
            'late': {'time': 99999, 'messages': ['x']},
            'junk': 'no',
        },
    })
    assert ok, err
    assert out['settings']['volume'] == 2.0
    assert out['settings']['admin_users'] == [12]
    tts = out['settings']['tts_settings']
    assert tts['voice_name'] == DEFAULT_VOICE
    assert tts['speed'] == 2.0
    assert tts['warning_time'] == 60
    assert out['timers'] == {'good': {'time': 30, 'messages': ['hi'], 'category': TimerCategory.REMINDER.value}}


def test_validate_config_rejects_bad_shapes():
    group = make_group()
    assert not group.validate_config([])[0]
    assert not group.validate_config({'settings': {}})[0]
    assert not group.validate_config({'settings': {}, 'timers': {'a': {'time': -1, 'message': 'x'}}})[0]
