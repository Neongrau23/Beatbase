"""Tests fuer den search_queue-Tracking-Layer."""

import sqlite3
import time
from pathlib import Path

import pytest

from beatbase.extractor import search_queue


@pytest.fixture
def db_path(tmp_path, monkeypatch) -> Path:
    """Biegt search_queue.DB_PATH auf eine tmp-Datei um."""
    path = tmp_path / "search_queue.db"
    monkeypatch.setattr(search_queue, "DB_PATH", path)
    return path


def _read(db_path: Path, track_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM search_queue WHERE track_id = ?", (track_id,)
    ).fetchone()
    conn.close()
    assert row is not None
    return dict(row)


def test_generate_id_is_deterministic_and_22_chars():
    a = search_queue.generate_id("Strobe", "deadmau5")
    b = search_queue.generate_id("Strobe", "deadmau5")
    assert a == b
    assert len(a) == 22


def test_generate_id_differs_per_input():
    a = search_queue.generate_id("Strobe", "deadmau5")
    b = search_queue.generate_id("Animals", "Martin Garrix")
    assert a != b


def test_enqueue_inserts_rows_and_returns_count(db_path):
    inserted = search_queue.enqueue(
        [
            {"id": "t1", "song": "A", "artist": "X"},
            {"id": "t2", "song": "B", "artist": "Y", "isrc": "USXX", "release_date": "2024-01"},
        ]
    )
    assert inserted == 2
    row = _read(db_path, "t2")
    assert row["song"] == "B"
    assert row["artist"] == "Y"
    assert row["isrc"] == "USXX"
    assert row["release_date"] == "2024-01"
    assert row["tunebat_status"] is None
    assert row["attempts"] == 0


def test_enqueue_is_idempotent_on_track_id(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    inserted_second = search_queue.enqueue(
        [
            {"id": "t1", "song": "A neu", "artist": "X neu"},  # darf nicht ueberschreiben
            {"id": "t2", "song": "B", "artist": "Y"},
        ]
    )
    assert inserted_second == 1
    row = _read(db_path, "t1")
    assert row["song"] == "A"  # Originalwert bleibt


def test_enqueue_empty_list_returns_zero(db_path):
    assert search_queue.enqueue([]) == 0


def test_fetch_pending_returns_rows_with_any_null(db_path):
    search_queue.enqueue(
        [
            {"id": "t1", "song": "A", "artist": "X"},
            {"id": "t2", "song": "B", "artist": "Y"},
        ]
    )
    search_queue.update_statuses(
        "t1",
        {"tunebat": "ok", "songstats": "ok", "genius": "ok", "songbpm": "ok"},
    )
    pending = search_queue.fetch_pending()
    ids = [row["track_id"] for row in pending]
    assert ids == ["t2"]


def test_fetch_pending_ignores_no_match_and_ok(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses(
        "t1",
        {"tunebat": "ok", "songstats": "no_match", "genius": "ok", "songbpm": "no_match"},
    )
    assert search_queue.fetch_pending() == []


def test_fetch_pending_respects_limit(db_path):
    search_queue.enqueue(
        [
            {"id": "t1", "song": "A", "artist": "X"},
            {"id": "t2", "song": "B", "artist": "Y"},
            {"id": "t3", "song": "C", "artist": "Z"},
        ]
    )
    assert len(search_queue.fetch_pending(limit=2)) == 2


def test_update_statuses_increments_attempts(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses("t1", {"tunebat": "ok"})
    search_queue.update_statuses("t1", {"songstats": "fail: Timeout"})
    row = _read(db_path, "t1")
    assert row["tunebat_status"] == "ok"
    assert row["songstats_status"] == "fail: Timeout"
    assert row["attempts"] == 2
    assert row["last_attempt_at"] is not None


def test_update_statuses_ignores_unknown_sources(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses("t1", {"tunebat": "ok", "bogus": "ok"})
    row = _read(db_path, "t1")
    assert row["tunebat_status"] == "ok"
    # Nur eine echte Source -> attempts++
    assert row["attempts"] == 1


def test_update_statuses_with_only_unknown_sources_is_noop(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses("t1", {"bogus": "ok"})
    row = _read(db_path, "t1")
    assert row["attempts"] == 0


def test_reset_fails_targets_only_fail_rows(db_path):
    search_queue.enqueue(
        [
            {"id": "t1", "song": "A", "artist": "X"},
            {"id": "t2", "song": "B", "artist": "Y"},
        ]
    )
    search_queue.update_statuses("t1", {"tunebat": "fail: Timeout", "songstats": "ok"})
    search_queue.update_statuses("t2", {"tunebat": "no_match", "songstats": "ok"})
    reset = search_queue.reset_fails()
    assert reset == 1
    row1 = _read(db_path, "t1")
    row2 = _read(db_path, "t2")
    assert row1["tunebat_status"] is None  # zurueckgesetzt
    assert row1["songstats_status"] == "ok"
    assert row2["tunebat_status"] == "no_match"  # no_match bleibt


def test_reset_fails_by_source(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses(
        "t1",
        {"tunebat": "fail: x", "songstats": "fail: y", "genius": "ok"},
    )
    reset = search_queue.reset_fails(source="tunebat")
    assert reset == 1
    row = _read(db_path, "t1")
    assert row["tunebat_status"] is None
    assert row["songstats_status"] == "fail: y"  # nicht ruecksetzt
    assert row["genius_status"] == "ok"


def test_reset_fails_rejects_unknown_source(db_path):
    with pytest.raises(ValueError):
        search_queue.reset_fails(source="bogus")


def test_status_summary_counts_per_source(db_path):
    search_queue.enqueue(
        [
            {"id": "t1", "song": "A", "artist": "X"},
            {"id": "t2", "song": "B", "artist": "Y"},
            {"id": "t3", "song": "C", "artist": "Z"},
        ]
    )
    search_queue.update_statuses(
        "t1",
        {"tunebat": "ok", "songstats": "ok", "genius": "ok", "songbpm": "ok"},
    )
    search_queue.update_statuses(
        "t2",
        {"tunebat": "no_match", "songstats": "fail: Timeout"},
    )
    summary = search_queue.status_summary()
    assert summary["total"] == 3
    tb = summary["sources"]["tunebat"]
    assert tb["ok"] == 1 and tb["no_match"] == 1 and tb["pending"] == 1 and tb["fail"] == 0
    ss = summary["sources"]["songstats"]
    assert ss["ok"] == 1 and ss["fail"] == 1 and ss["pending"] == 1
    sb = summary["sources"]["songbpm"]
    assert sb["pending"] == 2 and sb["ok"] == 1


def test_attempts_starts_at_zero_for_new_track(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    row = _read(db_path, "t1")
    assert row["attempts"] == 0
    assert row["last_attempt_at"] is None
    assert row["queued_at"] is not None


def test_last_attempt_at_changes_between_updates(db_path):
    search_queue.enqueue([{"id": "t1", "song": "A", "artist": "X"}])
    search_queue.update_statuses("t1", {"tunebat": "ok"})
    first = _read(db_path, "t1")["last_attempt_at"]
    # Mikropause, damit der ISO-Timestamp garantiert different ist
    time.sleep(0.01)
    search_queue.update_statuses("t1", {"songstats": "ok"})
    second = _read(db_path, "t1")["last_attempt_at"]
    assert first != second
