"""Tests fuer die lokale Song-Summary-SQLite-DB (core/songs_db.py)."""

import json
import sqlite3
from pathlib import Path

import pytest

from beatbase.processor import songs_db


@pytest.fixture
def db_path(tmp_path, monkeypatch) -> Path:
    """Biegt songs_db.DB_PATH auf eine tmp-Datei um."""
    path = tmp_path / "songs.db"
    monkeypatch.setattr(songs_db, "DB_PATH", path)
    return path


def _read_row(db_path: Path, track_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM songs WHERE track_id = ?", (track_id,)
    ).fetchone()
    conn.close()
    assert row is not None
    return dict(row)


def test_save_creates_db_and_inserts_row(db_path):
    songs_db.save_song_summary("track-1", {"meta": {"title": "Song A"}})
    assert db_path.exists()
    row = _read_row(db_path, "track-1")
    assert row["title"] == "Song A"
    assert row["saved_at"] is not None


def test_save_persists_full_schema(db_path):
    summary = {
        "meta": {
            "title": "Title",
            "artist": "Artist",
            "album": "Album",
            "release_date": "2024-01-01",
            "isrc": "USXX123",
            "explicit": "False",
            "label": "Label",
            "genres": "House, Techno",
        },
        "music_theory": {
            "bpm": "120",
            "key": "C major",
            "camelot": "8B",
            "duration": "3:45",
            "popularity": "70",
        },
        "audio_features": {
            "acousticness": "0.1",
            "danceability": "0.8",
            "energy": "0.9",
            "instrumentalness": "0.0",
            "liveness": "0.2",
            "speechiness": "0.05",
            "happiness": "0.6",
            "loudness": "-5",
        },
        "analysis": "Some analysis text",
        "lyrics": [{"line": "first"}, {"line": "second"}],
        "album_tracklist": [{"track": 1}],
        "credits": {"producer": "P"},
        "links": {
            "genius": "https://g",
            "spotify": "https://s",
            "tunebat": "https://t",
            "songstats": "https://ss",
            "songbpm": "https://sb",
        },
    }
    songs_db.save_song_summary("track-2", summary)

    row = _read_row(db_path, "track-2")
    assert row["title"] == "Title"
    assert row["artist"] == "Artist"
    assert row["genres"] == "House, Techno"
    assert row["bpm"] == "120"
    assert row["camelot"] == "8B"
    assert row["energy"] == "0.9"
    assert row["analysis"] == "Some analysis text"
    assert row["link_spotify"] == "https://s"


def test_lyrics_tracklist_credits_serialized_as_json(db_path):
    songs_db.save_song_summary(
        "track-3",
        {
            "lyrics": [{"line": "a"}],
            "album_tracklist": [{"track": 1, "title": "X"}],
            "credits": {"producer": "P"},
        },
    )
    row = _read_row(db_path, "track-3")
    assert json.loads(row["lyrics"]) == [{"line": "a"}]
    assert json.loads(row["album_tracklist"]) == [{"track": 1, "title": "X"}]
    assert json.loads(row["credits"]) == {"producer": "P"}


def test_missing_fields_become_null(db_path):
    songs_db.save_song_summary("track-4", {})
    row = _read_row(db_path, "track-4")
    assert row["title"] is None
    assert row["bpm"] is None
    assert row["link_genius"] is None
    # Leere JSON-Defaults fuer Listen/Dicts
    assert json.loads(row["lyrics"]) == []
    assert json.loads(row["album_tracklist"]) == []
    assert json.loads(row["credits"]) == {}


def test_same_track_id_overwrites(db_path):
    songs_db.save_song_summary("track-5", {"meta": {"title": "Old"}})
    songs_db.save_song_summary("track-5", {"meta": {"title": "New"}})

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM songs WHERE track_id = ?", ("track-5",)
    ).fetchone()[0]
    conn.close()
    assert count == 1

    row = _read_row(db_path, "track-5")
    assert row["title"] == "New"


def test_unicode_roundtrip(db_path):
    songs_db.save_song_summary(
        "track-6",
        {"meta": {"title": "Söng über alles", "artist": "Ärtist"}},
    )
    row = _read_row(db_path, "track-6")
    assert row["title"] == "Söng über alles"
    assert row["artist"] == "Ärtist"


def test_create_table_idempotent(db_path):
    """Mehrfache Calls duerfen das Schema nicht crashen."""
    songs_db.save_song_summary("track-7", {"meta": {"title": "A"}})
    songs_db.save_song_summary("track-8", {"meta": {"title": "B"}})

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
    conn.close()
    assert count == 2
