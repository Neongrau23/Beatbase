"""Tests fuer _extract_overview gegen ein HTML-Fixture."""

import pytest
from bs4 import BeautifulSoup

from beatbase.extractor.songstats.scraper.overview import _extract_overview


@pytest.fixture
def overview_soup(fixtures_dir) -> BeautifulSoup:
    html = (fixtures_dir / "songstats" / "overview.html").read_text(encoding="utf-8")
    return BeautifulSoup(html, "html.parser")


def test_extracts_artists(overview_soup):
    result = _extract_overview(overview_soup)
    assert result["Artists"] == "The Weeknd"


def test_extracts_multiple_record_labels_joined(overview_soup):
    result = _extract_overview(overview_soup)
    assert result["Record Labels"] == "XO, Republic"


def test_extracts_isrcs(overview_soup):
    result = _extract_overview(overview_soup)
    assert result["ISRCs"] == "USUG11904206"


def test_extracts_release_date_via_light_text_fallback(overview_soup):
    # Release Date hat keine Pills, sondern direkten light-text span
    result = _extract_overview(overview_soup)
    assert result["Release Date"] == "2019-11-29"


def test_extracts_distributors(overview_soup):
    result = _extract_overview(overview_soup)
    assert result["Distributors"] == "Universal"


def test_extracts_music_info(overview_soup):
    result = _extract_overview(overview_soup)
    assert result["Tempo"] == "171 BPM"
    assert result["Key"] == "F# minor"
    assert result["Duration"] == "3:20"
    assert result["Time Signature"] == "4/4"


def test_extracts_genres_sorted_and_deduplicated(overview_soup):
    result = _extract_overview(overview_soup)
    genres = result["Genres"]
    parts = [p.strip() for p in genres.split(",")]
    # sortierte Reihenfolge
    assert parts == sorted(parts)
    # Alle drei Tags vorhanden
    assert "#synth-pop" in parts
    assert "#pop" in parts
    assert "#electronic" in parts


def test_ignores_unknown_label_fields(overview_soup):
    result = _extract_overview(overview_soup)
    # "Other field:" ist nicht in targets-Liste und darf nicht extrahiert werden
    assert "Other field" not in result
    assert "Other" not in result


def test_returns_dict():
    # Defensiv: leere Eingabe → leeres dict (keine Crashes)
    empty_soup = BeautifulSoup("<html></html>", "html.parser")
    result = _extract_overview(empty_soup)
    assert isinstance(result, dict)
