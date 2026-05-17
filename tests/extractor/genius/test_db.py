"""Tests fuer den Genius-Artist-Songs-Store (genius/db.py)."""

import sqlite3
from pathlib import Path

import pytest

from beatbase.extractor.genius import db as genius_db


@pytest.fixture
def db_path(tmp_path, monkeypatch) -> Path:
    """Biegt genius_db.DB_PATH auf eine tmp-Datei um."""
    path = tmp_path / "genius.db"
    monkeypatch.setattr(genius_db, "DB_PATH", path)
    return path


def _fetch_all(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM songs ORDER BY genius_url").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_empty_list_returns_zero_and_skips_db(db_path):
    inserted = genius_db.save_artist_songs([])
    assert inserted == 0
    assert not db_path.exists()


def test_save_single_song(db_path):
    songs = [{"title": "Araña", "subtitle": "Uve Sad", "url": "https://genius.com/Uve-sad-arana-lyrics"}]
    inserted = genius_db.save_artist_songs(songs)

    assert inserted == 1
    rows = _fetch_all(db_path)
    assert len(rows) == 1
    assert rows[0] == {
        "genius_url": "https://genius.com/Uve-sad-arana-lyrics",
        "song": "Araña",
        "artist": "Uve Sad",
    }


def test_save_multiple_songs_returns_count(db_path):
    songs = [
        {"title": "A", "subtitle": "X", "url": "https://genius.com/a"},
        {"title": "B", "subtitle": "X", "url": "https://genius.com/b"},
        {"title": "C", "subtitle": "X", "url": "https://genius.com/c"},
    ]
    assert genius_db.save_artist_songs(songs) == 3
    assert len(_fetch_all(db_path)) == 3


def test_duplicate_url_is_ignored(db_path):
    """Zweimal die gleiche URL einfuegen → nur eine Zeile, Insert-Count 0."""
    song = {"title": "A", "subtitle": "X", "url": "https://genius.com/a"}
    assert genius_db.save_artist_songs([song]) == 1
    assert genius_db.save_artist_songs([song]) == 0
    assert len(_fetch_all(db_path)) == 1


def test_duplicate_url_keeps_first_entry(db_path):
    """Spaeterer Eintrag mit gleicher URL aber anderem Titel ueberschreibt nicht."""
    genius_db.save_artist_songs(
        [{"title": "Original", "subtitle": "Artist A", "url": "https://genius.com/x"}]
    )
    genius_db.save_artist_songs(
        [{"title": "Changed", "subtitle": "Artist B", "url": "https://genius.com/x"}]
    )
    rows = _fetch_all(db_path)
    assert len(rows) == 1
    assert rows[0]["song"] == "Original"
    assert rows[0]["artist"] == "Artist A"


def test_partial_duplicates_in_batch(db_path):
    genius_db.save_artist_songs(
        [
            {"title": "A", "subtitle": "X", "url": "https://genius.com/a"},
            {"title": "B", "subtitle": "X", "url": "https://genius.com/b"},
        ]
    )
    inserted = genius_db.save_artist_songs(
        [
            {"title": "B", "subtitle": "X", "url": "https://genius.com/b"},
            {"title": "C", "subtitle": "X", "url": "https://genius.com/c"},
        ]
    )
    assert inserted == 1
    assert {r["genius_url"] for r in _fetch_all(db_path)} == {
        "https://genius.com/a",
        "https://genius.com/b",
        "https://genius.com/c",
    }


def test_song_without_url_is_skipped(db_path):
    songs = [
        {"title": "A", "subtitle": "X", "url": None},
        {"title": "B", "subtitle": "X", "url": "https://genius.com/b"},
    ]
    assert genius_db.save_artist_songs(songs) == 1
    rows = _fetch_all(db_path)
    assert len(rows) == 1
    assert rows[0]["genius_url"] == "https://genius.com/b"


def test_song_without_title_is_skipped(db_path):
    songs = [
        {"title": None, "subtitle": "X", "url": "https://genius.com/a"},
        {"title": "B", "subtitle": "X", "url": "https://genius.com/b"},
    ]
    assert genius_db.save_artist_songs(songs) == 1


def test_missing_subtitle_falls_back_to_empty_string(db_path):
    """Ohne Subtitle (mini_card-subtitle fehlt) soll der Eintrag trotzdem rein."""
    genius_db.save_artist_songs(
        [{"title": "A", "subtitle": None, "url": "https://genius.com/a"}]
    )
    rows = _fetch_all(db_path)
    assert rows[0]["artist"] == ""


def test_schema_created_on_first_call(db_path):
    assert not db_path.exists()
    genius_db.save_artist_songs(
        [{"title": "A", "subtitle": "X", "url": "https://genius.com/a"}]
    )
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    assert ("songs",) in tables
