"""Tests fuer extract_artist_links_from_header."""

import pytest
from bs4 import BeautifulSoup

from beatbase.extractor.genius.scraper.extractor import extract_artist_links_from_header


@pytest.fixture
def header_soup(fixtures_dir) -> BeautifulSoup:
    html = (fixtures_dir / "genius" / "song_header_credit_list.html").read_text(encoding="utf-8")
    return BeautifulSoup(html, "html.parser")


def test_extracts_all_artist_links(header_soup):
    urls = extract_artist_links_from_header(header_soup)
    assert urls == [
        "https://genius.com/artists/Ssio",
        "https://genius.com/artists/Kiz",
    ]


def test_dedupes_repeated_links(header_soup):
    # Die Fixture enthaelt den SSIO-Link in zwei Containern (einmal absolut,
    # einmal relativ). Nach Absolutierung muss er nur einmal vorkommen.
    urls = extract_artist_links_from_header(header_soup)
    assert urls.count("https://genius.com/artists/Ssio") == 1


def test_returns_empty_list_when_container_missing():
    soup = BeautifulSoup("<html><body><div>no header</div></body></html>", "html.parser")
    assert extract_artist_links_from_header(soup) == []
