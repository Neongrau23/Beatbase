"""Tests fuer den BrowserPool (Worker-Lifecycle, Dispatching, Recycle, Crash-Recovery).

Wir mocken ``sync_playwright`` und ``_create_context_for`` komplett aus, damit
keine echten Browser-Prozesse gestartet werden. ``_run_extractor`` wird via
Monkeypatch durch eine deterministische Stub-Funktion ersetzt.
"""

import threading
from unittest.mock import MagicMock

import pytest
from playwright._impl._errors import TargetClosedError

from beatbase.extractor import browser_pool, orchestrator
from beatbase.extractor.browser_pool import BrowserPool, ExtractorWorker
from beatbase.extractor.orchestrator import ExtractorSpec
from beatbase.shared.utils.playwright_errors import is_browser_closed_error


# DEF: Hilfs-Spec ohne echte search_fn
def _spec(name: str) -> ExtractorSpec:
    return ExtractorSpec(
        name=name,
        label=name.title(),
        enabled=True,
        search_fn=lambda song, artists, **kw: {"ok": True},
    )


# DEF: Fake-Playwright-Context — gibt Mock-Pages zurueck
class _FakeContext:
    def __init__(self):
        self.pages: list = []
        self.closed = False

    def new_page(self):
        page = MagicMock(name="page")
        self.pages.append(page)
        return page

    def close(self):
        self.closed = True


# DEF: Fake sync_playwright-Kontextmanager
class _FakePW:
    def __enter__(self):
        return MagicMock(name="playwright")

    def __exit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """Retry-Pause auf 0 setzen — Tests sollen nicht 5s schlafen."""
    monkeypatch.setattr(browser_pool, "BATCH_RETRY_DELAY_SECONDS", 0)


@pytest.fixture
def crash_max_retries(monkeypatch):
    """Setzt BATCH_CRASH_MAX_RETRIES auf einen Wunschwert fuer den Test."""

    def setter(value: int):
        monkeypatch.setattr(browser_pool, "BATCH_CRASH_MAX_RETRIES", value)

    return setter


@pytest.fixture(autouse=True)
def _mock_playwright(monkeypatch):
    """Ersetzt sync_playwright und _create_context_for durch Fakes —
    so laufen Worker durch, ohne echte Browser hochzuziehen.
    """
    monkeypatch.setattr(browser_pool, "sync_playwright", lambda: _FakePW())
    monkeypatch.setattr(
        browser_pool, "_create_context_for", lambda *a, **kw: _FakeContext()
    )


# DEF: Restricts EXTRACTORS auf das Set, das der Test braucht
@pytest.fixture
def fake_specs(monkeypatch):
    """Liefert eine reduzierte EXTRACTORS-Liste — Tests pinnen so genau die
    Quellen fest, die sie auch beibringen wollen.
    """

    def install(specs: list[ExtractorSpec]):
        monkeypatch.setattr(orchestrator, "EXTRACTORS", specs)
        monkeypatch.setattr(browser_pool, "EXTRACTORS", specs)

    return install


# SECTION: ExtractorWorker


def test_worker_processes_single_track(monkeypatch, fake_specs):
    fake_specs([_spec("tunebat")])
    monkeypatch.setattr(
        browser_pool, "_run_extractor", lambda spec, track, page, headless: "ok"
    )

    worker = ExtractorWorker(_spec("tunebat"), headless=True)
    worker.start()
    try:
        fut = worker.submit({"id": "t1", "song": "A", "artists": []})
        assert fut.result(timeout=5) == "ok"
    finally:
        worker.shutdown()
    assert not worker.is_alive()


def test_worker_processes_multiple_tracks_in_order(monkeypatch, fake_specs):
    fake_specs([_spec("tunebat")])
    seen: list[str] = []

    def stub(spec, track, page, headless):
        seen.append(track["id"])
        return "ok"

    monkeypatch.setattr(browser_pool, "_run_extractor", stub)

    worker = ExtractorWorker(_spec("tunebat"), headless=True)
    worker.start()
    try:
        futs = [worker.submit({"id": f"t{i}", "song": "A", "artists": []}) for i in range(5)]
        results = [f.result(timeout=5) for f in futs]
    finally:
        worker.shutdown()

    assert results == ["ok"] * 5
    assert seen == [f"t{i}" for i in range(5)]


def test_worker_retries_on_fail(monkeypatch, fake_specs):
    fake_specs([_spec("songbpm")])
    attempts = {"n": 0}

    def stub(spec, track, page, headless):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return "fail: transient: boom"
        return "ok"

    monkeypatch.setattr(browser_pool, "_run_extractor", stub)

    worker = ExtractorWorker(_spec("songbpm"), headless=True)
    worker.start()
    try:
        fut = worker.submit({"id": "t1", "song": "A", "artists": []})
        assert fut.result(timeout=5) == "ok"
    finally:
        worker.shutdown()
    assert attempts["n"] == 2


def test_worker_retries_on_target_closed_error(monkeypatch, fake_specs, crash_max_retries):
    """TargetClosedError beim 1. Aufruf -> Browser neu hochziehen -> 2. Aufruf klappt."""
    crash_max_retries(3)
    fake_specs([_spec("songbpm")])

    contexts_opened: list[_FakeContext] = []

    def context_factory(*a, **kw):
        ctx = _FakeContext()
        contexts_opened.append(ctx)
        return ctx

    monkeypatch.setattr(browser_pool, "_create_context_for", context_factory)

    call_count = {"n": 0}

    def stub(spec, track, page, headless):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise TargetClosedError("Page.goto: Target page, context or browser has been closed")
        return "ok"

    monkeypatch.setattr(browser_pool, "_run_extractor", stub)

    worker = ExtractorWorker(_spec("songbpm"), headless=True)
    worker.start()
    try:
        fut = worker.submit({"id": "t1", "song": "A", "artists": []})
        status = fut.result(timeout=5)
    finally:
        worker.shutdown()

    assert status == "ok"
    # Initial-Context + ein neuer nach dem Crash = 2 insgesamt
    assert len(contexts_opened) == 2
    assert contexts_opened[0].closed is True
    assert call_count["n"] == 2


def test_worker_gives_up_after_max_retries(monkeypatch, fake_specs, crash_max_retries):
    """Wenn jeder Versuch crasht, faellt der Worker nach N Versuchen auf 'fail:' zurueck."""
    crash_max_retries(3)
    fake_specs([_spec("tunebat")])

    contexts_opened: list[_FakeContext] = []

    def context_factory(*a, **kw):
        ctx = _FakeContext()
        contexts_opened.append(ctx)
        return ctx

    monkeypatch.setattr(browser_pool, "_create_context_for", context_factory)

    call_count = {"n": 0}

    def stub(spec, track, page, headless):
        call_count["n"] += 1
        raise TargetClosedError("Target closed")

    monkeypatch.setattr(browser_pool, "_run_extractor", stub)

    worker = ExtractorWorker(_spec("tunebat"), headless=True)
    worker.start()
    try:
        fut = worker.submit({"id": "t1", "song": "A", "artists": []})
        status = fut.result(timeout=5)
    finally:
        worker.shutdown()

    assert status.startswith("fail: BrowserCrash nach 3 Versuchen")
    # Initial + 3 Reopens (auch nach dem letzten Crash, damit naechster Track lebt)
    assert len(contexts_opened) == 4
    assert call_count["n"] == 3


def test_worker_does_not_reopen_on_fail_status(monkeypatch, fake_specs, crash_max_retries):
    """Wenn _run_extractor 'fail:'-String zurueckgibt (nicht raised), wird der Browser
    NICHT neu hochgezogen — nur der existierende fail-Retry greift.
    """
    crash_max_retries(3)
    fake_specs([_spec("genius")])

    contexts_opened: list[_FakeContext] = []

    def context_factory(*a, **kw):
        ctx = _FakeContext()
        contexts_opened.append(ctx)
        return ctx

    monkeypatch.setattr(browser_pool, "_create_context_for", context_factory)
    monkeypatch.setattr(
        browser_pool,
        "_run_extractor",
        lambda spec, track, page, headless: "fail: ScraperError: nope",
    )

    worker = ExtractorWorker(_spec("genius"), headless=True)
    worker.start()
    try:
        fut = worker.submit({"id": "t1", "song": "A", "artists": []})
        status = fut.result(timeout=5)
    finally:
        worker.shutdown()

    assert status.startswith("fail: ScraperError")
    # Nur der initiale Context — kein Reopen, weil keine Exception bubbelte
    assert len(contexts_opened) == 1


def test_worker_crash_retries_zero_means_one_attempt(monkeypatch, fake_specs, crash_max_retries):
    """BATCH_CRASH_MAX_RETRIES=0 deaktiviert den Retry — genau 1 Versuch."""
    crash_max_retries(0)
    fake_specs([_spec("songstats")])

    call_count = {"n": 0}

    def stub(spec, track, page, headless):
        call_count["n"] += 1
        raise TargetClosedError("Target closed")

    monkeypatch.setattr(browser_pool, "_run_extractor", stub)

    worker = ExtractorWorker(_spec("songstats"), headless=True)
    worker.start()
    try:
        fut = worker.submit({"id": "t1", "song": "A", "artists": []})
        status = fut.result(timeout=5)
    finally:
        worker.shutdown()

    assert status.startswith("fail: BrowserCrash nach 1 Versuchen")
    assert call_count["n"] == 1


# SECTION: is_browser_closed_error helper


def test_is_browser_closed_error_detects_target_closed():
    assert is_browser_closed_error(TargetClosedError("Browser closed")) is True


def test_is_browser_closed_error_detects_classic_message():
    """Auch ein generischer PlaywrightError mit klassischer Message wird erkannt."""
    from playwright.sync_api import Error as PlaywrightError

    assert (
        is_browser_closed_error(
            PlaywrightError("Page.goto: Target page, context or browser has been closed")
        )
        is True
    )


def test_is_browser_closed_error_returns_false_for_other_errors():
    assert is_browser_closed_error(RuntimeError("something else")) is False
    assert is_browser_closed_error(ValueError("nope")) is False


# SECTION: BrowserPool


def test_pool_starts_one_worker_per_enabled_source(monkeypatch, fake_specs):
    fake_specs([_spec("tunebat"), _spec("songstats"), _spec("genius"), _spec("songbpm")])
    monkeypatch.setattr(
        browser_pool, "_run_extractor", lambda spec, track, page, headless: "ok"
    )

    pool = BrowserPool(headless=True)
    pool.start()
    try:
        assert set(pool._workers.keys()) == {"tunebat", "songstats", "genius", "songbpm"}
        for w in pool._workers.values():
            assert w.is_alive()
    finally:
        pool.shutdown()


def test_pool_submit_routes_to_correct_worker(monkeypatch, fake_specs):
    fake_specs([_spec("tunebat"), _spec("songstats")])
    seen_by_source: dict[str, list[str]] = {"tunebat": [], "songstats": []}
    lock = threading.Lock()

    def stub(spec, track, page, headless):
        with lock:
            seen_by_source[spec.name].append(track["id"])
        return "ok"

    monkeypatch.setattr(browser_pool, "_run_extractor", stub)

    pool = BrowserPool(headless=True)
    pool.start()
    try:
        f1 = pool.submit("tunebat", {"id": "t1", "song": "A", "artists": []})
        f2 = pool.submit("songstats", {"id": "t1", "song": "A", "artists": []})
        assert f1.result(timeout=5) == "ok"
        assert f2.result(timeout=5) == "ok"
    finally:
        pool.shutdown()

    assert seen_by_source["tunebat"] == ["t1"]
    assert seen_by_source["songstats"] == ["t1"]


def test_pool_submit_raises_for_unknown_source(monkeypatch, fake_specs):
    fake_specs([_spec("tunebat")])
    monkeypatch.setattr(
        browser_pool, "_run_extractor", lambda spec, track, page, headless: "ok"
    )

    pool = BrowserPool(headless=True)
    pool.start()
    try:
        with pytest.raises(KeyError):
            pool.submit("genius", {"id": "t1", "song": "A", "artists": []})
    finally:
        pool.shutdown()


def test_pool_recycle_replaces_all_workers(monkeypatch, fake_specs):
    fake_specs([_spec("tunebat"), _spec("songstats")])
    monkeypatch.setattr(
        browser_pool, "_run_extractor", lambda spec, track, page, headless: "ok"
    )

    pool = BrowserPool(headless=True)
    pool.start()
    try:
        old_workers = dict(pool._workers)
        pool.recycle()
        new_workers = pool._workers

        assert set(new_workers.keys()) == set(old_workers.keys())
        for name in old_workers:
            assert new_workers[name] is not old_workers[name]
            assert new_workers[name].is_alive()
            assert not old_workers[name].is_alive()
    finally:
        pool.shutdown()


def test_pool_shutdown_joins_all_workers(monkeypatch, fake_specs):
    fake_specs([_spec("tunebat"), _spec("songstats"), _spec("genius")])
    monkeypatch.setattr(
        browser_pool, "_run_extractor", lambda spec, track, page, headless: "ok"
    )

    pool = BrowserPool(headless=True)
    pool.start()
    workers = list(pool._workers.values())
    pool.shutdown()

    for w in workers:
        assert not w.is_alive()
    assert pool._workers == {}


def test_pool_respects_disabled_sources(monkeypatch, fake_specs):
    """Quellen mit enabled=False werden uebersprungen."""
    fake_specs(
        [
            _spec("tunebat"),
            ExtractorSpec(
                name="songstats",
                label="Songstats",
                enabled=False,
                search_fn=lambda *a, **kw: None,
            ),
        ]
    )
    monkeypatch.setattr(
        browser_pool, "_run_extractor", lambda spec, track, page, headless: "ok"
    )

    pool = BrowserPool(headless=True)
    pool.start()
    try:
        assert "tunebat" in pool._workers
        assert "songstats" not in pool._workers
        assert not pool.has("songstats")
    finally:
        pool.shutdown()
