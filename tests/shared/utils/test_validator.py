"""Unit-Tests fuer das Fuzzy-Match-Scoring."""

import pytest

from beatbase.shared.utils.validator import calculate_validation_score


def test_exact_match_returns_high_score():
    # Identische Texte -> Score nahe 1.0 (vor Boni)
    text = "blinding lights the weeknd"
    score = calculate_validation_score(text, text, [])
    assert score >= 0.99


def test_completely_different_returns_low_score():
    score = calculate_validation_score("abcdef", "uvwxyz", [])
    assert score < 0.3


def test_artist_bonus_added_when_artist_in_text():
    base = calculate_validation_score("song title weeknd", "song title", [])
    boosted = calculate_validation_score("song title weeknd", "song title", ["Weeknd"])
    assert boosted == pytest.approx(base + 0.2, abs=0.01)


def test_artist_bonus_per_artist():
    base = calculate_validation_score("song a b", "song", [])
    two = calculate_validation_score("song a b", "song", ["A", "B"])
    assert two == pytest.approx(base + 0.4, abs=0.01)


def test_artist_bonus_case_insensitive():
    score_lower = calculate_validation_score("song the weeknd", "song", ["the weeknd"])
    score_upper = calculate_validation_score("song the weeknd", "song", ["The Weeknd"])
    assert score_lower == pytest.approx(score_upper, abs=0.01)


def test_artist_not_in_text_no_bonus():
    base = calculate_validation_score("song title", "song title", [])
    with_missing = calculate_validation_score("song title", "song title", ["Drake"])
    assert with_missing == pytest.approx(base, abs=0.01)


def test_remix_bonus():
    import difflib
    text = "song remix"
    target = "song"
    base_difflib = difflib.SequenceMatcher(None, target, text).ratio()
    actual = calculate_validation_score(text, target, [])
    # Erwartet: difflib-Score + 0.1 fuer Remix-Bonus
    assert actual == pytest.approx(base_difflib + 0.1, abs=0.01)


def test_edit_bonus():
    import difflib
    text = "song edit"
    target = "song"
    base_difflib = difflib.SequenceMatcher(None, target, text).ratio()
    actual = calculate_validation_score(text, target, [])
    assert actual == pytest.approx(base_difflib + 0.1, abs=0.01)


def test_custom_artist_bonus_value():
    text = "song artist name"
    target = "song"
    no_bonus = calculate_validation_score(text, target, [])
    with_bonus = calculate_validation_score(text, target, ["artist"], artist_bonus=0.5)
    # Differenz ist exakt der custom artist_bonus
    assert with_bonus == pytest.approx(no_bonus + 0.5, abs=0.01)


def test_case_insensitive_text_comparison():
    score_lower = calculate_validation_score("BLINDING LIGHTS", "blinding lights", [])
    score_upper = calculate_validation_score("blinding lights", "blinding lights", [])
    assert score_lower == pytest.approx(score_upper, abs=0.01)
