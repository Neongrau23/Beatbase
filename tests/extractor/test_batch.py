"""Tests fuer den Batch-Modus (CSV-Parser, run/retry/Pipeline-Integration)."""

import sqlite3
from pathlib import Path

import pytest

from beatbase.extractor import batch, search_queue


@pytest.fixture
def db_path(tmp_path, monkeypatch) -> Path:
    """Frische search_queue.db pro Test."""
    path = tmp_path / "search_queue.db"
    monkeypatch.setattr(search_queue, "DB_PATH", path)
    return path


def _read(db_path: Path, track_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM search_queue WHERE track_id = ?", (track_id,)).fetchone()
    conn.close()
    assert row is not None
    return dict(row)


# SECTION: _row_to_track


def test_row_to_track_full_row():
    track = batch._row_to_track(
        {
            "id": "abc",
            "song": "Strobe",
            "artist": "deadmau5",
            "isrc": "CABNS0900086",
            "release_date": "2010-09-13",
        }
    )
    assert track == {
        "id": "abc",
        "song": "Strobe",
        "artist": "deadmau5",
        "isrc": "CABNS0900086",
        "release_date": "2010-09-13",
    }


def test_row_to_track_generates_id_if_missing():
    track = batch._row_to_track({"id": "", "song": "Strobe", "artist": "deadmau5"})
    assert track is not None
    expected = search_queue.generate_id("Strobe", "deadmau5")
    assert track["id"] == expected
    assert len(track["id"]) == 22


def test_row_to_track_returns_none_without_song():
    assert batch._row_to_track({"song": "", "artist": "X"}) is None
    assert batch._row_to_track({"artist": "X"}) is None


def test_row_to_track_returns_none_without_artist():
    assert batch._row_to_track({"song": "A", "artist": ""}) is None
    assert batch._row_to_track({"song": "A"}) is None


def test_row_to_track_normalizes_empty_optional_fields():
    track = batch._row_to_track({"song": "A", "artist": "X", "isrc": "", "release_date": ""})
    assert track is not None
    assert track["isrc"] is None
    assert track["release_date"] is None


def test_row_to_track_strips_whitespace():
    track = batch._row_to_track({"id": "  abc  ", "song": "  A  ", "artist": "  X  "})
    assert track == {
        "id": "abc",
        "song": "A",
        "artist": "X",
        "isrc": None,
        "release_date": None,
    }


# SECTION: add_from_file


def test_add_from_file_inserts_rows(tmp_path, db_path):
    csv_file = tmp_path / "tracks.csv"
    csv_file.write_text(
        "id,song,artist,isrc,release_date\nabc,Strobe,deadmau5,,\n,Animals,Martin Garrix,,\n",
        encoding="utf-8",
    )
    inserted = batch.add_from_file(csv_file)
    assert inserted == 2
    row = _read(db_path, "abc")
    assert row["song"] == "Strobe"


def test_add_from_file_skips_rows_without_song_or_artist(tmp_path, db_path):
    csv_file = tmp_path / "tracks.csv"
    csv_file.write_text(
        "id,song,artist\n"
        ",Strobe,deadmau5\n"
        ",,Nobody\n"  # song fehlt
        ",Solo,\n",  # artist fehlt
        encoding="utf-8",
    )
    inserted = batch.add_from_file(csv_file)
    assert inserted == 1


def test_add_from_file_handles_bom(tmp_path, db_path):
    """Excel speichert CSV oft mit UTF-8-BOM — DictReader muss damit klarkommen."""
    csv_file = tmp_path / "tracks.csv"
    csv_file.write_bytes(b"\xef\xbb\xbfid,song,artist\nx,Hit,Artist\n")
    inserted = batch.add_from_file(csv_file)
    assert inserted == 1
    assert _read(db_path, "x")["song"] == "Hit"


def test_add_from_file_idempotent_on_rerun(tmp_path, db_path):
    csv_file = tmp_path / "tracks.csv"
    csv_file.write_text("id,song,artist\nabc,Strobe,deadmau5\n", encoding="utf-8")
    assert batch.add_from_file(csv_file) == 1
    assert batch.add_from_file(csv_file) == 0


# SECTION: run() — Pipeline-Integration mit Mock fuer handle_new_track


def test_run_processes_only_pending_tracks(db_path, monkeypatch):
    """run() darf bereits terminale Tracks nicht erneut anfassen."""
    search_queue.enqueue(
        [
            {"id": "t1", "song": "A", "artist": "X"},
            {"id": "t2", "song": "B", "artist": "Y"},
        ]
    )
    # t1 vollstaendig fertig
    search_queue.update_statuses(
        "t1",
        {"tunebat": "ok", "songstats": "ok", "genius": "ok", "songbpm": "ok"},
    )

    called: list[str] = []

    def fake_handle(track, headless):
        called.append(track["id"])
        return {"tunebat": "ok", "songstats": "ok", "genius": "ok", "songbpm": "ok"}

    monkeypatch.setattr(batch, "handle_new_track", fake_handle)
    batch.run(headless=True)

    assert called == ["t2"]
    row = _read(db_path, "t2")
    assert row["tunebat_status"] == "ok"
    assert row["attempts"] == 1


def test_run_splits_semicolon_separated_artists(db_path, monkeypatch):
    search_queue.enqueue([{"id": "t1", "song": "Sun Goes Down", "artist": "David Guetta; Showtek"}])
    captured: dict = {}

    def fake_handle(track, headless):
        captured.update(track)
        return {"tunebat": "ok"}

    monkeypatch.setattr(batch, "handle_new_track", fake_handle)
    batch.run(headless=True)

    assert captured["artists"] == ["David Guetta", "Showtek"]


def test_run_records_partial_fail_on_handle_crash(db_path, monkeypatch):
    """Wenn handle_new_track selbst crasht, werden nur die noch nicht
    terminalen Quellen mit fail markiert."""
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    # tunebat war beim letzten Lauf schon ok — soll nicht ueberschrieben werden
    search_queue.update_statuses("t1", {"tunebat": "ok"})

    def boom(track, headless):
        raise RuntimeError("Browser kaputt")

    monkeypatch.setattr(batch, "handle_new_track", boom)
    batch.run(headless=True)

    row = _read(db_path, "t1")
    assert row["tunebat_status"] == "ok"  # bleibt
    assert row["songstats_status"].startswith("fail: RuntimeError")
    assert row["genius_status"].startswith("fail: RuntimeError")
    assert row["songbpm_status"].startswith("fail: RuntimeError")


def test_run_empty_queue_is_noop(db_path, monkeypatch):
    called: list = []
    monkeypatch.setattr(batch, "handle_new_track", lambda track, headless: called.append(track) or {})
    batch.run(headless=True)
    assert called == []


def test_run_passes_headless_through(db_path, monkeypatch):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    seen: list = []

    def fake_handle(track, headless):
        seen.append(headless)
        return {"tunebat": "ok"}

    monkeypatch.setattr(batch, "handle_new_track", fake_handle)
    batch.run(headless=True)
    assert seen == [True]


def test_run_respects_limit(db_path, monkeypatch):
    search_queue.enqueue(
        [
            {"id": "t1", "song": "A", "artist": "X"},
            {"id": "t2", "song": "B", "artist": "Y"},
            {"id": "t3", "song": "C", "artist": "Z"},
        ]
    )
    called: list = []
    monkeypatch.setattr(
        batch,
        "handle_new_track",
        lambda track, headless: called.append(track["id"]) or {"tunebat": "ok"},
    )
    batch.run(headless=True, limit=2)
    assert len(called) == 2


# SECTION: retry()


def test_retry_resets_fails_and_runs(db_path, monkeypatch):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses(
        "t1",
        {"tunebat": "fail: x", "songstats": "ok", "genius": "ok", "songbpm": "ok"},
    )

    called: list = []
    monkeypatch.setattr(
        batch,
        "handle_new_track",
        lambda track, headless: called.append(track["id"]) or {"tunebat": "ok"},
    )
    batch.retry(headless=True)

    assert called == ["t1"]
    row = _read(db_path, "t1")
    assert row["tunebat_status"] == "ok"
    assert row["songstats_status"] == "ok"  # nicht ueberschrieben


def test_retry_with_source_filters(db_path, monkeypatch):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses("t1", {"tunebat": "fail: x", "songstats": "fail: y", "genius": "ok"})
    monkeypatch.setattr(batch, "handle_new_track", lambda track, headless: {"tunebat": "ok"})
    batch.retry(source="tunebat", headless=True)

    row = _read(db_path, "t1")
    assert row["tunebat_status"] == "ok"
    # songstats bleibt fail, weil reset_fails(source='tunebat') es nicht beruehrt
    assert row["songstats_status"] == "fail: y"
