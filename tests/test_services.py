from services import TTSService


def test_rate_and_pitch_strings():
    assert TTSService._get_rate_string(1.0) == "+0%"
    assert TTSService._get_rate_string(1.15) == "+15%"
    assert TTSService._get_rate_string(0.75) == "-25%"
    assert TTSService._get_pitch_string(1.0) == "+0Hz"
    assert TTSService._get_pitch_string(0.9) == "-10Hz"


def test_numbers_become_words():
    assert TTSService._convert_numbers_to_words("in 10 seconds") == "in ten seconds"
    assert TTSService._convert_numbers_to_words("level 6 and 42") == "level six and forty-two"
    assert TTSService._convert_numbers_to_words("year 1999") == "year 1999"


def test_process_message_applies_pronunciations():
    svc = TTSService()
    out = svc._process_message("Fangtooth in 30", {'custom_pronunciations': {'Fangtooth': 'Fang tooth'}})
    assert out == "Fang tooth in thirty"
    assert svc._process_message("30", {'number_to_words': False}) == "30"
