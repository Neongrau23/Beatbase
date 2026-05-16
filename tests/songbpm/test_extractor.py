"""Tests fuer extract_song_info gegen ein HTML-Fixture.

Die echte Funktion macht requests.get(url) — wir mocken den HTTP-Layer
und liefern unser Fixture-HTML als Response-Body.
"""

import pytest

from beatbase.songbpm.scraper import extractor as extractor_module
from beatbase.songbpm.scraper.extractor import extract_song_info


class MockResponse:
    """Minimal-Stub fuer requests.Response."""

    def __init__(self, html: str, status_code: int = 200):
        self.status_code = status_code
        self.content = html.encode("utf-8")


@pytest.fixture
def mocked_html(fixtures_dir, monkeypatch):
    """Mockt requests.get so, dass es immer das Fixture-HTML liefert."""
    html = (fixtures_dir / "songbpm" / "detail.html").read_text(encoding="utf-8")

    def fake_get(url, timeout=None):
        return MockResponse(html, 200)

    monkeypatch.setattr(extractor_module, "requests", type("R", (), {"get": fake_get}))
    return html


def test_extracts_song_title(mocked_html):
    result = extract_song_info("https://fake.url/song")
    assert result["title"] == "Blinding Lights"


def test_extracts_artist(mocked_html):
    result = extract_song_info("https://fake.url/song")
    assert result["artist"] == "The Weeknd"


def test_extracts_metrics(mocked_html):
    result = extract_song_info("https://fake.url/song")
    assert result["key"] == "F# minor"
    assert result["duration"] == "3:20"
    assert result["bpm"] == "171"


def test_extracts_description(mocked_html):
    result = extract_song_info("https://fake.url/song")
    assert "energetic" in result["description"]
    assert "synth-pop" in result["description"]


def test_extracts_spotify_url(mocked_html):
    result = extract_song_info("https://fake.url/song")
    assert result["spotify_url"] == "https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b"


def test_includes_source_url(mocked_html):
    result = extract_song_info("https://fake.url/song")
    assert result["url"] == "https://fake.url/song"


def test_no_none_values_in_result(mocked_html):
    result = extract_song_info("https://fake.url/song")
    # extract_song_info filtert None-Werte heraus
    assert all(v is not None for v in result.values())


def test_http_failure_returns_none(monkeypatch):
    """Status-Code != 200 → None."""

    def fake_get(url, timeout=None):
        return MockResponse("", status_code=500)

    monkeypatch.setattr(extractor_module, "requests", type("R", (), {"get": fake_get}))
    assert extract_song_info("https://fake.url/song") is None


def test_request_exception_returns_none(monkeypatch):
    """Wenn requests.get crasht, faengt extract_song_info die Exception ab."""

    def fake_get(url, timeout=None):
        raise ConnectionError("network down")

    monkeypatch.setattr(extractor_module, "requests", type("R", (), {"get": fake_get}))
    assert extract_song_info("https://fake.url/song") is None
