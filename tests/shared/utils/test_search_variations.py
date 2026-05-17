"""Unit-Tests fuer die Such-Variations-Helfer."""

import pytest

from beatbase.shared.utils.search_variations import (
    extract_featured_artists,
    generate_variations,
)


# SECTION: extract_featured_artists
class TestExtractFeaturedArtists:
    def test_feat_dot(self):
        assert extract_featured_artists("Song feat. Artist X") == ["Artist X"]

    def test_ft_dot(self):
        assert extract_featured_artists("Song ft. Artist X") == ["Artist X"]

    def test_with(self):
        assert extract_featured_artists("Song with Artist X") == ["Artist X"]

    def test_von(self):
        assert extract_featured_artists("Song von Artist X") == ["Artist X"]

    def test_no_feature_returns_empty(self):
        assert extract_featured_artists("Just a Song Title") == []

    def test_multiple_artists_with_ampersand(self):
        result = extract_featured_artists("Song feat. A & B")
        assert result == ["A", "B"]

    def test_multiple_artists_with_comma(self):
        result = extract_featured_artists("Song feat. A, B, C")
        assert result == ["A", "B", "C"]

    def test_multiple_artists_with_and(self):
        result = extract_featured_artists("Song feat. A and B")
        assert result == ["A", "B"]

    def test_multiple_artists_with_x(self):
        result = extract_featured_artists("Song feat. A x B")
        assert result == ["A", "B"]

    def test_strips_trailing_paren(self):
        # "Song (feat. X)" — der schließende Paren am Ende soll weg
        result = extract_featured_artists("Song (feat. Artist X)")
        assert result == ["Artist X"]

    def test_case_insensitive(self):
        assert extract_featured_artists("Song FEAT. X") == ["X"]
        assert extract_featured_artists("Song Ft. X") == ["X"]


# SECTION: generate_variations
class TestGenerateVariations:
    def test_includes_original(self):
        variations = generate_variations("My Song", ["Artist"])
        assert "My Song" in variations

    def test_returns_list(self):
        variations = generate_variations("Song", ["A"])
        assert isinstance(variations, list)
        assert all(isinstance(v, str) for v in variations)

    def test_deduplicates(self):
        variations = generate_variations("Song", ["A"])
        # Case-insensitive dedupe — keine zwei Eintraege duerfen lowercase gleich sein
        lower = [v.lower() for v in variations]
        assert len(lower) == len(set(lower))

    def test_respects_limit(self):
        variations = generate_variations("Song", ["A"], limit=3)
        assert len(variations) <= 3

    def test_handles_empty_artists(self):
        variations = generate_variations("Song", [])
        assert len(variations) > 0
        assert "Song" in variations

    def test_normalizes_unicode(self):
        # naïve -> naive
        variations = generate_variations("naïve", ["A"])
        # Mindestens eine Variation enthaelt die normalisierte Form
        assert any("naive" in v.lower() for v in variations)

    def test_typographic_apostrophe_replaced(self):
        # Curly apostrophe → straight in den abgeleiteten Variationen.
        # Das Original bleibt verbatim drin (raw_vars[0] = target_song), aber
        # alle daraus abgeleiteten Variationen nutzen den ASCII-Apostroph.
        variations = generate_variations("Don’t Stop", ["A"])
        ascii_variants = [v for v in variations if "Don't" in v]
        assert len(ascii_variants) > 0

    def test_strips_feat_block_from_core_title(self):
        variations = generate_variations("Hit Song feat. X", ["Main"])
        # Wenigstens eine Variation enthält "Hit Song" ohne "feat" — der core_title
        core_variants = [v for v in variations if "feat" not in v.lower()]
        assert len(core_variants) > 0
        assert any("Hit Song" in v for v in core_variants)

    def test_remix_tag_preserved_in_some_variation(self):
        variations = generate_variations("Song (Hardstyle Remix)", ["Artist"])
        # Mindestens eine Variation soll "Remix" enthalten
        assert any("remix" in v.lower() for v in variations)


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Song feat. X", ["X"]),
        ("Song ft. X", ["X"]),
        ("Song with X", ["X"]),
        ("Song von X", ["X"]),
        ("Plain Title", []),
    ],
)
def test_extract_featured_artists_parametrized(title, expected):
    assert extract_featured_artists(title) == expected
