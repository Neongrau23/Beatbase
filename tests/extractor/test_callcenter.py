"""Unit-Tests fuer das deklarative Callcenter-Schema."""

import json

from beatbase.extractor.callcenter import (
    LINKS,
    META,
    MUSIC_THEORY,
    FieldSpec,
    Source,
    _determine_release_date,
    _from_dict,
    _join_list,
    _pick,
    build_song_summary,
    get_summary_json,
)
from beatbase.extractor.hotline import bus


# SECTION: _join_list
class TestJoinList:
    def test_joins_non_empty_list(self):
        assert _join_list(["A", "B"]) == "A, B"

    def test_empty_list_returns_none(self):
        assert _join_list([]) is None

    def test_passes_through_string(self):
        assert _join_list("plain string") == "plain string"

    def test_none_returns_none(self):
        assert _join_list(None) is None

    def test_dict_returns_none(self):
        assert _join_list({"a": 1}) is None


# SECTION: _from_dict
class TestFromDict:
    def test_returns_subkey(self):
        transform = _from_dict("url")
        assert transform({"url": "https://x.com", "other": 1}) == "https://x.com"

    def test_missing_subkey_returns_none(self):
        transform = _from_dict("url")
        assert transform({"only": "this"}) is None

    def test_non_dict_returns_none(self):
        transform = _from_dict("url")
        assert transform("not a dict") is None
        assert transform(None) is None
        assert transform([1, 2, 3]) is None


# SECTION: _pick
class TestPick:
    def test_first_truthy_source_wins(self):
        bus.set("a", "key", "from_a")
        bus.set("b", "key", "from_b")
        spec = FieldSpec(sources=(Source("a", "key"), Source("b", "key")))
        assert _pick(spec) == "from_a"

    def test_skips_falsy_and_tries_next(self):
        bus.set("a", "key", "")  # falsy
        bus.set("b", "key", "from_b")
        spec = FieldSpec(sources=(Source("a", "key"), Source("b", "key")))
        assert _pick(spec) == "from_b"

    def test_skips_missing_and_tries_next(self):
        bus.set("b", "key", "from_b")
        spec = FieldSpec(sources=(Source("a", "key"), Source("b", "key")))
        assert _pick(spec) == "from_b"

    def test_applies_transform(self):
        bus.set("a", "key", ["x", "y"])
        spec = FieldSpec(sources=(Source("a", "key", transform=_join_list),))
        assert _pick(spec) == "x, y"

    def test_transform_returns_none_falls_to_next(self):
        bus.set("a", "key", [])  # empty list, transform returns None
        bus.set("b", "key", "from_b")
        spec = FieldSpec(sources=(
            Source("a", "key", transform=_join_list),
            Source("b", "key"),
        ))
        assert _pick(spec) == "from_b"

    def test_fallback_used_when_all_sources_empty(self):
        spec = FieldSpec(
            sources=(Source("a", "key"),),
            fallback=lambda: "fallback_value",
        )
        assert _pick(spec) == "fallback_value"

    def test_returns_none_without_fallback(self):
        spec = FieldSpec(sources=(Source("a", "key"),))
        assert _pick(spec) is None


# SECTION: _determine_release_date
class TestDetermineReleaseDate:
    def test_returns_none_for_empty_bus(self):
        assert _determine_release_date() is None

    def test_finds_release_date_in_any_source(self):
        bus.set("foo", "release_date", "2020-01-01")
        assert _determine_release_date() == "2020-01-01"

    def test_picks_oldest_across_sources(self):
        bus.set("a", "release_date", "2020-01-01")
        bus.set("b", "Release Date", "2019-12-31")
        bus.set("c", "Release date", "2018-06-15")
        assert _determine_release_date() == "2018-06-15"

    def test_ignores_non_dict_sources(self):
        # Direkt im storage manipulieren - Falsche Form
        bus.storage["weird"] = "not_a_dict"  # type: ignore[assignment]
        bus.set("good", "release_date", "2020-01-01")
        # Sollte nicht crashen
        assert _determine_release_date() == "2020-01-01"


# SECTION: build_song_summary (Integration)
class TestBuildSongSummary:
    def test_master_schema_keys_always_present(self):
        summary = build_song_summary()
        assert set(summary.keys()) == {
            "meta",
            "music_theory",
            "audio_features",
            "analysis",
            "lyrics",
            "album_tracklist",
            "artist_songs",
            "credits",
            "links",
        }

    def test_empty_bus_yields_all_none_meta(self):
        summary = build_song_summary()
        for value in summary["meta"].values():
            assert value is None

    def test_spotify_artists_joined_to_string(self):
        bus.set("spotify", "name", "Song")
        bus.set("spotify", "artists", ["A", "B"])
        summary = build_song_summary()
        assert summary["meta"]["title"] == "Song"
        assert summary["meta"]["artist"] == "A, B"

    def test_tunebat_album_overrides_spotify(self):
        bus.set("spotify", "album", "Spotify Album")
        bus.set("tunebat", "album", "Tunebat Album")
        summary = build_song_summary()
        assert summary["meta"]["album"] == "Tunebat Album"

    def test_spotify_release_date_overrides_songstats(self):
        bus.set("spotify", "release_date", "2019-11-29")
        bus.set("songstats", "Release Date", "2020-05-01")
        # tunebat zuerst, spotify zweitens, songstats drittens — tunebat fehlt also spotify
        summary = build_song_summary()
        assert summary["meta"]["release_date"] == "2019-11-29"

    def test_release_date_falls_back_to_oldest(self):
        # Keine direkte Quelle, aber Daten in beliebigen Source-Dicts
        bus.set("foo", "release_date", "2020-01-01")
        bus.set("bar", "Release Date", "2018-01-01")
        summary = build_song_summary()
        assert summary["meta"]["release_date"] == "2018-01-01"

    def test_audio_features_from_tunebat(self):
        bus.set("tunebat", "audio_features", {"energy": "85", "danceability": "72"})
        summary = build_song_summary()
        assert summary["audio_features"]["energy"] == "85"
        assert summary["audio_features"]["danceability"] == "72"
        # Nicht vorhandene Features sind None
        assert summary["audio_features"]["acousticness"] is None

    def test_genius_lyrics_credits_from_data_block(self):
        bus.set(
            "genius",
            "data",
            {
                "lyrics": [{"section": "[Verse]", "lines": ["..."]}],
                "credits": {"producers": ["X"]},
                "album_tracklist": [{"number": "1", "title": "..."}],
                "url": "https://genius.com/song",
            },
        )
        summary = build_song_summary()
        assert summary["lyrics"] == [{"section": "[Verse]", "lines": ["..."]}]
        assert summary["credits"] == {"producers": ["X"]}
        assert summary["album_tracklist"] == [{"number": "1", "title": "..."}]
        assert summary["links"]["genius"] == "https://genius.com/song"

    def test_songbpm_data_block_yields_analysis_and_url(self):
        bus.set("songbpm", "data", {"description": "energetic", "url": "https://sb.com"})
        summary = build_song_summary()
        assert summary["analysis"] == "energetic"
        assert summary["links"]["songbpm"] == "https://sb.com"

    def test_genius_url_prefers_data_block_over_flat(self):
        # Beide gesetzt — der nested data-Block hat Vorrang (historisches Verhalten)
        bus.set("genius", "data", {"url": "from_data"})
        bus.set("genius", "url", "from_flat")
        summary = build_song_summary()
        assert summary["links"]["genius"] == "from_data"

    def test_genius_url_falls_back_to_flat_if_no_data(self):
        bus.set("genius", "url", "from_flat")
        summary = build_song_summary()
        assert summary["links"]["genius"] == "from_flat"

    def test_lyrics_default_to_empty_list(self):
        summary = build_song_summary()
        assert summary["lyrics"] == []
        assert summary["album_tracklist"] == []
        assert summary["credits"] == {}


# SECTION: get_summary_json
class TestGetSummaryJson:
    def test_returns_valid_json_string(self):
        bus.set("spotify", "name", "Song")
        out = get_summary_json()
        parsed = json.loads(out)
        assert parsed["meta"]["title"] == "Song"

    def test_pretty_printed_with_indent(self):
        out = get_summary_json()
        assert "\n" in out  # Mehrzeilig => mit indent


# SECTION: Schema-Selbsttests (Sicherheitsnetz fuer Refactorings)
class TestSchemaShape:
    def test_meta_has_expected_fields(self):
        assert set(META.keys()) == {
            "title",
            "artist",
            "album",
            "release_date",
            "isrc",
            "explicit",
            "label",
            "genres",
        }

    def test_music_theory_has_expected_fields(self):
        assert set(MUSIC_THEORY.keys()) == {
            "bpm",
            "key",
            "camelot",
            "duration",
            "popularity",
        }

    def test_links_has_expected_fields(self):
        assert set(LINKS.keys()) == {
            "genius",
            "spotify",
            "tunebat",
            "songstats",
            "songbpm",
        }

    def test_every_fieldspec_has_at_least_one_source(self):
        for name, spec in {**META, **MUSIC_THEORY, **LINKS}.items():
            assert len(spec.sources) > 0, f"{name!r} has no sources"
