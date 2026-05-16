"""Tests fuer extrahiere_song_details_json gegen ein HTML-Fixture."""

import pytest
from bs4 import BeautifulSoup

from beatbase.genius.scraper.extractor import extrahiere_song_details_json


@pytest.fixture
def song_soup(fixtures_dir) -> BeautifulSoup:
    html = (fixtures_dir / "genius" / "song.html").read_text(encoding="utf-8")
    return BeautifulSoup(html, "html.parser")


def test_extracts_track_info_title(song_soup):
    result = extrahiere_song_details_json(song_soup)
    assert result["track_info"]["title"] == "Blinding Lights"


def test_extracts_track_info_artist(song_soup):
    result = extrahiere_song_details_json(song_soup)
    assert result["track_info"]["artist"] == "The Weeknd"


def test_extracts_track_info_views(song_soup):
    result = extrahiere_song_details_json(song_soup)
    assert result["track_info"]["views"] == "1.2M views"


def test_extracts_lyrics_grouped_by_section(song_soup):
    result = extrahiere_song_details_json(song_soup)
    sections = {entry["section"] for entry in result["lyrics"]}
    assert "[Intro]" in sections
    assert "[Verse 1]" in sections
    assert "[Chorus]" in sections


def test_lyrics_lines_per_section_correct(song_soup):
    result = extrahiere_song_details_json(song_soup)
    by_section = {entry["section"]: entry["lines"] for entry in result["lyrics"]}
    assert by_section["[Intro]"] == ["Yeah"]
    assert by_section["[Verse 1]"] == [
        "I've been tryna call",
        "I've been on my own for long enough",
    ]
    assert by_section["[Chorus]"] == ["I said, ooh, I'm blinded by the lights"]


def test_extracts_producers_credits(song_soup):
    result = extrahiere_song_details_json(song_soup)
    assert result["credits"]["producers"] == ["Max Martin", "Oscar Holter"]


def test_extracts_writers_credits(song_soup):
    result = extrahiere_song_details_json(song_soup)
    assert result["credits"]["writers"] == ["Abel Tesfaye"]


def test_credits_without_links_fall_back_to_text(song_soup):
    result = extrahiere_song_details_json(song_soup)
    # "Release Date" hat keinen Link, also Text-Fallback
    assert result["credits"]["release_date"] == ["November 29, 2019"]


def test_album_tracklist_has_three_tracks(song_soup):
    result = extrahiere_song_details_json(song_soup)
    assert len(result["album_tracklist"]) == 3


def test_album_tracklist_first_track_has_link(song_soup):
    result = extrahiere_song_details_json(song_soup)
    first = result["album_tracklist"][0]
    assert first["number"] == "1"
    assert first["title"] == "Alone Again"
    # Relative Links werden auf absolute umgewandelt
    assert first["link"].startswith("http")
    assert "/songs/alone-again" in first["link"]


def test_album_tracklist_link_makes_relative_absolute(song_soup):
    result = extrahiere_song_details_json(song_soup)
    for track in result["album_tracklist"]:
        link = track.get("link")
        if link is not None:
            assert link.startswith("http"), f"Link nicht absolut: {link}"


def test_album_tracklist_track_without_link_has_title(song_soup):
    result = extrahiere_song_details_json(song_soup)
    # Der dritte Track hat keinen <a>-Link
    third = result["album_tracklist"][2]
    assert third["number"] == "3"
    assert "Blinding Lights" in third["title"]


def test_fallback_message_when_no_lyrics_or_credits():
    empty_html = "<html><body><h1>Nothing</h1></body></html>"
    soup = BeautifulSoup(empty_html, "html.parser")
    result = extrahiere_song_details_json(soup)
    # Minimal-Rueckgabe bei Fehlschlag
    assert result["lyrics"] == [
        {"section": "[Info]", "lines": ["Keine Details Verfügbar"]}
    ]


def test_master_schema_keys_present(song_soup):
    result = extrahiere_song_details_json(song_soup)
    assert set(result.keys()) == {
        "track_info",
        "credits",
        "lyrics",
        "album_tracklist",
        "about",
    }
