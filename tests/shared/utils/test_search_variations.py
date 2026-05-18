"""Unit-Tests fuer die Such-Variations-Helfer."""

import pytest

from beatbase.shared.utils.search_variations import (
    _to_tunebat_slug,
    extract_featured_artists,
    generate_tunebat_variations,
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


# SECTION: _to_tunebat_slug
class TestToTunebatSlug:
    def test_basic_lowercase_and_join(self):
        assert _to_tunebat_slug("My Song", "Artist") == "my-song-artist"

    def test_unicode_umlauts_stripped(self):
        # NFKD + ASCII-Drop: 'ä' wird zu 'a', 'ö' zu 'o', 'ü' zu 'u'
        assert _to_tunebat_slug("Mädchen", "Künstler") == "madchen-kunstler"

    def test_apostrophe_becomes_dash(self):
        # Sonderzeichen → Leerzeichen → Bindestrich
        assert _to_tunebat_slug("Don't Stop", "Artist") == "don-t-stop-artist"

    def test_collapses_multiple_dashes(self):
        # Doppelte Bindestriche/Leerzeichen werden zu einem zusammengefasst
        assert _to_tunebat_slug("Song  --  Title", "A") == "song-title-a"

    def test_ignores_empty_parts(self):
        assert _to_tunebat_slug("Song", "", "Artist") == "song-artist"
        assert _to_tunebat_slug("Song", "   ", "Artist") == "song-artist"

    def test_strips_leading_trailing_dashes(self):
        # Sonderzeichen am Rand sollen nicht zu fuehrenden/folgenden Bindestrichen werden
        result = _to_tunebat_slug("!Song!", "Artist")
        assert not result.startswith("-")
        assert not result.endswith("-")


# SECTION: generate_tunebat_variations
class TestGenerateTunebatVariations:
    def test_album_variation_comes_first(self):
        # WHY: Album-Slugs sind auf Tunebat stabiler als Songtitel
        variations = generate_tunebat_variations("Mr. Brightside", ["The Killers"], "Hot Fuss")
        assert variations[0] == "hot-fuss-the-killers"

    def test_song_variation_present_when_album_given(self):
        variations = generate_tunebat_variations("Mr Brightside", ["The Killers"], "Hot Fuss")
        assert "mr-brightside-the-killers" in variations

    def test_no_album_falls_back_to_song(self):
        variations = generate_tunebat_variations("Mr Brightside", ["The Killers"], None)
        assert variations[0] == "mr-brightside-the-killers"
        assert not any("hot-fuss" in v for v in variations)

    def test_multi_artist_creates_main_artist_variant(self):
        # Mit Multi-Artist: zusaetzliche Variante nur mit Hauptkuenstler
        variations = generate_tunebat_variations(
            "Song", ["Main Artist", "Feature Artist"], "Album"
        )
        assert "album-main-artist-feature-artist" in variations
        assert "album-main-artist" in variations
        assert "song-main-artist-feature-artist" in variations
        assert "song-main-artist" in variations

    def test_single_artist_no_duplicate_main_only_variant(self):
        # Mit nur einem Artist gibt es keine separate main_artist-Variante
        variations = generate_tunebat_variations("Song", ["Artist"], "Album")
        # Es darf keinen Duplikat von "song-artist" geben
        assert len(variations) == len(set(variations))

    def test_whitespace_only_album_treated_as_none(self):
        # Spotify liefert gelegentlich " " als Album-Namen
        variations = generate_tunebat_variations("Song", ["Artist"], "   ")
        assert not any(v.startswith("-") for v in variations)
        # Erste Variation sollte song-basiert sein, nicht album-basiert
        assert variations[0] == "song-artist"

    def test_empty_album_string_treated_as_none(self):
        variations = generate_tunebat_variations("Song", ["Artist"], "")
        assert variations[0] == "song-artist"

    def test_deduplicates(self):
        # Wenn Album == Song, sollen Duplikate raus
        variations = generate_tunebat_variations("Song", ["Artist"], "Song")
        assert len(variations) == len(set(variations))

    def test_strips_feat_block_from_title(self):
        # 'feat. X' soll aus dem Slug fuer den Core-Title verschwinden
        variations = generate_tunebat_variations("Hit Song feat. Other", ["Main"], None)
        assert any(v == "hit-song-main" for v in variations)

    def test_unicode_normalization(self):
        # NFKD + ASCII-Drop: 'ä/ö/ü' verlieren ihre Diakritika, 'ß' wird gedroppt
        # (NFKD zerlegt 'ß' nicht in 'ss' — Trade-off des einfachen Encoders).
        variations = generate_tunebat_variations("Mädchen", ["Künstler"], "Grüße")
        assert variations[0] == "grue-kunstler"
        assert "madchen-kunstler" in variations

    def test_empty_artists_handled(self):
        variations = generate_tunebat_variations("Song", [], "Album")
        # Keine Crashes, leere Artists werden ignoriert
        assert all(isinstance(v, str) and v for v in variations)

    def test_returns_only_slug_format(self):
        # Kein Slug darf Leerzeichen enthalten
        variations = generate_tunebat_variations("Some Song Title", ["Some Artist"], "Some Album")
        assert all(" " not in v for v in variations)
        assert all(v == v.lower() for v in variations)
