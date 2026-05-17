"""Tests fuer den file-basierten IPC-Layer.

Der env-Backend nutzt PowerShell-Subprozesse und wird hier nicht getestet.
"""

import json

import pytest

from beatbase.shared.now_playing import (
    SENTINEL_NONE,
    clear_now_playing,
    read_now_playing,
    read_now_playing_data,
    write_now_playing,
)


@pytest.fixture
def ipc_file_in_tmp(tmp_path, monkeypatch):
    """IPC im file-Mode + CWD im tmp_path."""
    monkeypatch.setattr("beatbase.shared.now_playing.IPC_MODE", "file")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_write_and_read_roundtrip(ipc_file_in_tmp):
    write_now_playing("Song A", ["Artist 1", "Artist 2"])
    data = read_now_playing_data()
    assert data == {"song": "Song A", "artists": ["Artist 1", "Artist 2"]}


def test_write_persists_as_json(ipc_file_in_tmp):
    write_now_playing("Song", ["A"])
    path = ipc_file_in_tmp / "now_playing.txt"
    assert path.exists()
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content == {"song": "Song", "artists": ["A"]}


def test_write_default_artists_empty_list(ipc_file_in_tmp):
    write_now_playing("Song A")
    data = read_now_playing_data()
    assert data == {"song": "Song A", "artists": []}


def test_clear_writes_sentinel(ipc_file_in_tmp):
    write_now_playing("Song", ["A"])
    clear_now_playing()
    path = ipc_file_in_tmp / "now_playing.txt"
    assert path.read_text(encoding="utf-8") == SENTINEL_NONE


def test_read_sentinel_returns_none_song(ipc_file_in_tmp):
    clear_now_playing()
    data = read_now_playing_data()
    assert data == {"song": None, "artists": []}


def test_read_missing_file_returns_empty(ipc_file_in_tmp):
    # now_playing.txt existiert noch nicht
    data = read_now_playing_data()
    assert data == {"song": None, "artists": []}


def test_read_legacy_string_format_falls_back(ipc_file_in_tmp):
    # Vor JSON gab es das Format "Song von Artist"
    path = ipc_file_in_tmp / "now_playing.txt"
    path.write_text("Old Song von Old Artist", encoding="utf-8")
    data = read_now_playing_data()
    assert data == {"song": "Old Song", "artists": ["Old Artist"]}


def test_read_unparseable_string_returns_as_song(ipc_file_in_tmp):
    path = ipc_file_in_tmp / "now_playing.txt"
    path.write_text("just a plain string without separator", encoding="utf-8")
    data = read_now_playing_data()
    assert data == {"song": "just a plain string without separator", "artists": []}


def test_read_now_playing_string_wrapper_with_artists(ipc_file_in_tmp):
    write_now_playing("Title", ["A1", "A2"])
    assert read_now_playing() == "Title von A1, A2"


def test_read_now_playing_string_wrapper_without_artists(ipc_file_in_tmp):
    write_now_playing("Title", [])
    assert read_now_playing() == "Title"


def test_read_now_playing_returns_sentinel_if_empty(ipc_file_in_tmp):
    assert read_now_playing() == SENTINEL_NONE


def test_atomic_write_cleans_up_temp(ipc_file_in_tmp):
    write_now_playing("Song", ["A"])
    # Atomic write: temp file darf nicht zurueckbleiben
    tmp_file = ipc_file_in_tmp / "now_playing.txt.tmp"
    assert not tmp_file.exists()


def test_unicode_in_song_and_artists(ipc_file_in_tmp):
    write_now_playing("Söng über alles", ["Ärtist"])
    data = read_now_playing_data()
    assert data == {"song": "Söng über alles", "artists": ["Ärtist"]}
