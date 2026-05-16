"""Tests fuer den Tunebat-Suchergebnis-Store (tunebat/db.py)."""

import json
import sqlite3
from pathlib import Path

import pytest

from beatbase.tunebat import db as tunebat_db


@pytest.fixture
def db_path(tmp_path, monkeypatch) -> Path:
    """Biegt tunebat_db.DB_PATH auf eine tmp-Datei um."""
    path = tmp_path / "tunebat_searches.db"
    monkeypatch.setattr(tunebat_db, "DB_PATH", path)
    return path


def _fetch_all(db_path: Path, search_term: str | None = None) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if search_term is None:
        rows = conn.execute("SELECT * FROM search_results").fetchall()
    else:
        rows = conn.execute("SELECT * FROM search_results WHERE search_term = ?", (search_term,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_empty_results_skips_db_creation(db_path):
    """Bei leerer Result-Liste darf die DB nicht angelegt werden."""
    tunebat_db.save_search_results("any query", [])
    assert not db_path.exists()


def test_save_single_result(db_path):
    result = {
        "title": "Song A",
        "artists": ["Artist 1"],
        "key": "C major",
        "bpm": 120,
        "camelot": "8B",
        "popularity": 75,
        "imageUrl": "https://img",
        "tunebatUrl": "https://info",
        "spotifyUrl": "https://spotify",
        "songstatsUrl": "https://songstats",
    }
    tunebat_db.save_search_results("song a artist 1", [result])

    rows = _fetch_all(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["search_term"] == "song a artist 1"
    assert row["title"] == "Song A"
    assert row["bpm"] == 120
    assert row["camelot"] == "8B"
    assert row["tunebat_url"] == "https://info"
    assert row["songstats_url"] == "https://songstats"
    assert row["searched_at"] is not None


def test_artists_serialized_as_json(db_path):
    tunebat_db.save_search_results(
        "q",
        [{"title": "T", "artists": ["A1", "A2", "A3"]}],
    )
    row = _fetch_all(db_path)[0]
    assert json.loads(row["artists"]) == ["A1", "A2", "A3"]


def test_artists_default_empty_list(db_path):
    tunebat_db.save_search_results("q", [{"title": "T"}])
    row = _fetch_all(db_path)[0]
    assert json.loads(row["artists"]) == []


def test_save_multiple_results_in_one_call(db_path):
    results = [{"title": f"Song {i}", "artists": [f"A{i}"], "bpm": 100 + i} for i in range(5)]
    tunebat_db.save_search_results("batch", results)

    rows = _fetch_all(db_path, search_term="batch")
    assert len(rows) == 5
    assert {r["title"] for r in rows} == {f"Song {i}" for i in range(5)}


def test_repeat_save_appends_rows(db_path):
    """Anders als songs_db ist tunebat_db append-only."""
    tunebat_db.save_search_results("q", [{"title": "T"}])
    tunebat_db.save_search_results("q", [{"title": "T"}])
    rows = _fetch_all(db_path, search_term="q")
    assert len(rows) == 2


def test_missing_fields_become_null(db_path):
    tunebat_db.save_search_results("q", [{"title": "Only Title"}])
    row = _fetch_all(db_path)[0]
    assert row["title"] == "Only Title"
    assert row["key"] is None
    assert row["bpm"] is None
    assert row["camelot"] is None
    assert row["popularity"] is None
    assert row["image_url"] is None
    assert row["spotify_url"] is None


def test_search_term_index_exists(db_path):
    """Der Index auf search_term soll bei der Tabellenanlage mit erzeugt werden."""
    tunebat_db.save_search_results("q", [{"title": "T"}])
    conn = sqlite3.connect(db_path)
    indexes = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='search_results'").fetchall()
    conn.close()
    index_names = {row[0] for row in indexes}
    assert "idx_search_term" in index_names


def test_unicode_in_title_and_artists(db_path):
    tunebat_db.save_search_results(
        "söng",
        [{"title": "Söng über alles", "artists": ["Ärtist"]}],
    )
    row = _fetch_all(db_path)[0]
    assert row["title"] == "Söng über alles"
    assert json.loads(row["artists"]) == ["Ärtist"]
