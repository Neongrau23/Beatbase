"""Tests fuer den parallelen Batch-Pfad (2-Phasen-Pipeline + Retry)."""

import threading

import pytest

from beatbase.extractor import orchestrator, parallel
from beatbase.extractor.hotline import bus
from beatbase.extractor.orchestrator import ExtractorSpec


def _spec(name: str, fn, *, store=False, direct_url_from=None) -> ExtractorSpec:
    return ExtractorSpec(
        name=name,
        label=name.title(),
        enabled=True,
        search_fn=fn,
        store_under_data_key=store,
        direct_url_from=direct_url_from,
    )


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """Retry-Pause auf 0 setzen, damit Tests nicht in echte Sekunden warten."""
    monkeypatch.setattr(parallel, "BATCH_RETRY_DELAY_SECONDS", 0)


@pytest.fixture(autouse=True)
def _isolate_side_effects(monkeypatch):
    """IPC und Processor aus dem Spiel nehmen — wir testen nur die Pipeline."""
    monkeypatch.setattr(parallel, "_publish_now_playing", lambda *a, **kw: None)
    monkeypatch.setattr(parallel, "_handoff_to_processor", lambda *a, **kw: None)


# DEF: Hilfs-Pipeline mit 4 Specs (Tunebat fuer Phase 1, Rest fuer Phase 2)
def _install_specs(monkeypatch, tunebat_fn, songstats_fn, genius_fn, songbpm_fn):
    specs = [
        _spec("tunebat", tunebat_fn),
        _spec(
            "songstats",
            songstats_fn,
            direct_url_from=("tunebat", "songstats_url"),
        ),
        _spec("genius", genius_fn, store=True),
        _spec("songbpm", songbpm_fn, store=True),
    ]
    monkeypatch.setattr(orchestrator, "EXTRACTORS", specs)
    monkeypatch.setattr(parallel, "EXTRACTORS", specs)


def test_phase1_runs_before_phase2_and_direct_url_is_threaded(monkeypatch):
    """Tunebat muss komplett durch sein, bevor Songstats startet — und der
    `songstats_url`-Wert aus dem Bus muss bei Songstats als `direct_url` ankommen.
    """
    sequence: list[str] = []

    def tunebat(song, artists, **kw):
        sequence.append("tunebat-start")
        sequence.append("tunebat-end")
        return {"songstats_url": "https://songstats/x", "bpm": "120"}

    songstats_kwargs: dict = {}

    def songstats(song, artists, **kw):
        sequence.append("songstats")
        songstats_kwargs.update(kw)
        return {"ok": True}

    _install_specs(
        monkeypatch,
        tunebat,
        songstats,
        lambda song, artists, **kw: {"lyrics": []},
        lambda song, artists, **kw: {"description": "vibey"},
    )

    statuses = parallel.handle_new_track_parallel(
        {"id": "t1", "song": "A", "artists": ["X"]}, headless=True
    )

    assert statuses["tunebat"] == "ok"
    assert statuses["songstats"] == "ok"
    # Tunebat ist fertig, bevor Songstats anfaengt — sonst waere die Reihenfolge anders.
    assert sequence.index("tunebat-end") < sequence.index("songstats")
    # Cross-Extractor-Optimierung: direct_url ist durchgereicht.
    assert songstats_kwargs.get("direct_url") == "https://songstats/x"


def test_phase2_extractors_run_concurrently(monkeypatch):
    """Songstats, Genius, SongBPM laufen parallel — die Summe ihrer Laufzeiten
    muss deutlich groesser sein als die Wallclock-Zeit der Phase.
    """
    barrier = threading.Barrier(3)

    def waits(song, artists, **kw):
        # Jeder Worker wartet, bis alle drei am Barrier sind. Wenn sie
        # sequenziell laufen wuerden, wuerde das deadlocken (timeout).
        barrier.wait(timeout=5)
        return {"ok": True}

    _install_specs(
        monkeypatch,
        lambda song, artists, **kw: {"songstats_url": None, "bpm": "120"},
        waits,
        waits,
        waits,
    )

    statuses = parallel.handle_new_track_parallel(
        {"id": "t1", "song": "A", "artists": ["X"]}, headless=True
    )
    assert statuses["songstats"] == "ok"
    assert statuses["genius"] == "ok"
    assert statuses["songbpm"] == "ok"


def test_retry_on_fail_recovers(monkeypatch):
    """Crash beim ersten Aufruf, ok beim zweiten — finaler Status muss "ok" sein."""
    attempts = {"songbpm": 0}

    def flaky_songbpm(song, artists, **kw):
        attempts["songbpm"] += 1
        if attempts["songbpm"] == 1:
            raise RuntimeError("transient")
        return {"description": "fine now"}

    _install_specs(
        monkeypatch,
        lambda song, artists, **kw: {"songstats_url": None, "bpm": "120"},
        lambda song, artists, **kw: {"ok": True},
        lambda song, artists, **kw: {"lyrics": []},
        flaky_songbpm,
    )

    statuses = parallel.handle_new_track_parallel(
        {"id": "t1", "song": "A", "artists": ["X"]}, headless=True
    )
    assert statuses["songbpm"] == "ok"
    assert attempts["songbpm"] == 2


def test_retry_persists_fail_after_second_attempt(monkeypatch):
    """Bleibt der Crash beim Retry bestehen, wird ``fail:`` zurueckgegeben."""
    attempts = {"genius": 0}

    def always_crashes(song, artists, **kw):
        attempts["genius"] += 1
        raise RuntimeError("permanent")

    _install_specs(
        monkeypatch,
        lambda song, artists, **kw: {"songstats_url": None, "bpm": "120"},
        lambda song, artists, **kw: {"ok": True},
        always_crashes,
        lambda song, artists, **kw: {"description": "x"},
    )

    statuses = parallel.handle_new_track_parallel(
        {"id": "t1", "song": "A", "artists": ["X"]}, headless=True
    )
    assert statuses["genius"].startswith("fail: RuntimeError")
    assert attempts["genius"] == 2  # erst Versuch + ein Retry


def test_no_match_is_not_retried(monkeypatch):
    """`no_match` ist eine definitive Antwort der Quelle — kein Retry."""
    attempts = {"genius": 0}

    def returns_nothing(song, artists, **kw):
        attempts["genius"] += 1
        return None

    _install_specs(
        monkeypatch,
        lambda song, artists, **kw: {"songstats_url": None, "bpm": "120"},
        lambda song, artists, **kw: {"ok": True},
        returns_nothing,
        lambda song, artists, **kw: {"description": "x"},
    )

    statuses = parallel.handle_new_track_parallel(
        {"id": "t1", "song": "A", "artists": ["X"]}, headless=True
    )
    assert statuses["genius"] == "no_match"
    assert attempts["genius"] == 1  # nicht wiederholt


def test_bus_is_cleared_between_tracks(monkeypatch):
    """``bus.clear()`` muss am Anfang von handle_new_track_parallel laufen."""
    bus.set("alt", "stale", "von letztem Track")

    _install_specs(
        monkeypatch,
        lambda song, artists, **kw: {"songstats_url": None, "bpm": "120"},
        lambda song, artists, **kw: {"ok": True},
        lambda song, artists, **kw: {"lyrics": []},
        lambda song, artists, **kw: {"description": "x"},
    )

    parallel.handle_new_track_parallel(
        {"id": "t1", "song": "A", "artists": ["X"]}, headless=True
    )
    assert bus.get("alt", "stale", default=None) is None
