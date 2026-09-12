import pytest

from timer import GameTimer


def test_parse_time_accepts_m_ss():
    assert GameTimer.parse_time("0:00") == 0
    assert GameTimer.parse_time("4:30") == 270
    assert GameTimer.parse_time("12:05") == 725
    assert GameTimer.parse_time(" 1:01 ") == 61


@pytest.mark.parametrize("bad", ["", "5", "5:60", "-1:00", "a:b", "1:2:3"])
def test_parse_time_rejects_garbage(bad):
    with pytest.raises(ValueError):
        GameTimer.parse_time(bad)


def test_start_offsets_clock_and_stop_resets():
    t = GameTimer(1)
    assert not t.is_active and t.get_game_time() == 0
    t.start("4:30", "nitro")
    assert t.is_active and t.mode == "nitro"
    assert 270 <= t.get_game_time() <= 271
    t.announced_events.add("x")
    t.stop()
    assert not t.is_active and t.get_game_time() == 0 and not t.announced_events


def test_format_time():
    assert GameTimer.format_time(0) == "0:00"
    assert GameTimer.format_time(725) == "12:05"
