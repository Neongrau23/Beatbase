"""Status-Mapping in `_run_extractor`: ok / no_match / fail."""

from beatbase.extractor import orchestrator
from beatbase.extractor.hotline import bus
from beatbase.extractor.orchestrator import ExtractorSpec, _run_extractor


def _make_spec(search_fn, *, name="dummy", store=False, direct_url_from=None):
    return ExtractorSpec(
        name=name,
        label=name.title(),
        enabled=True,
        search_fn=search_fn,
        store_under_data_key=store,
        direct_url_from=direct_url_from,
    )


def test_returns_ok_and_writes_to_bus_on_hit():
    spec = _make_spec(lambda song, artists, **kw: {"bpm": "120", "key": "C"})
    status = _run_extractor(spec, {"song": "X", "artists": ["Y"]}, page=None, headless=True)
    assert status == "ok"
    assert bus.get("dummy", "bpm") == "120"
    assert bus.get("dummy", "key") == "C"


def test_returns_no_match_on_falsy_result():
    spec = _make_spec(lambda song, artists, **kw: None)
    status = _run_extractor(spec, {"song": "X", "artists": []}, page=None, headless=True)
    assert status == "no_match"


def test_returns_no_match_on_empty_dict():
    """Ein leeres dict ist truthy in Python — aber `not result` greift es ab.

    `{}` ist falsy, also gilt es als no_match.
    """
    spec = _make_spec(lambda song, artists, **kw: {})
    status = _run_extractor(spec, {"song": "X", "artists": []}, page=None, headless=True)
    assert status == "no_match"


def test_returns_fail_on_exception():
    def crashes(song, artists, **kw):
        raise RuntimeError("Browser ist tot")

    spec = _make_spec(crashes)
    status = _run_extractor(spec, {"song": "X", "artists": []}, page=None, headless=True)
    assert status.startswith("fail: RuntimeError")
    assert "Browser ist tot" in status


def test_store_under_data_key_sets_data_in_bus():
    payload = {"lyrics": ["a", "b"], "url": "https://genius/x"}
    spec = _make_spec(
        lambda song, artists, **kw: payload, name="genius", store=True
    )
    status = _run_extractor(spec, {"song": "X", "artists": []}, page=None, headless=True)
    assert status == "ok"
    # Sowohl "data" als auch die flachen Keys werden gesetzt
    assert bus.get("genius", "data") == payload
    assert bus.get("genius", "lyrics") == ["a", "b"]
    assert bus.get("genius", "url") == "https://genius/x"


def test_direct_url_from_is_passed_as_kwarg():
    """Wenn die Spec `direct_url_from` setzt, wird der Wert aus dem Bus als
    `direct_url` an die Search-Funktion durchgereicht."""
    bus.set("tunebat", "songstats_url", "https://songstats/abc")

    seen: dict = {}

    def capture(song, artists, **kw):
        seen.update(kw)
        return {"ok": True}

    spec = _make_spec(
        capture,
        name="songstats",
        direct_url_from=("tunebat", "songstats_url"),
    )
    status = _run_extractor(spec, {"song": "X", "artists": []}, page=None, headless=True)
    assert status == "ok"
    assert seen.get("direct_url") == "https://songstats/abc"


def test_handle_new_track_returns_status_dict(monkeypatch):
    """End-to-end (gemockt): handle_new_track sammelt pro aktivem Extractor einen Status."""
    fake_specs = [
        _make_spec(lambda song, artists, **kw: {"bpm": "120"}, name="tunebat"),
        _make_spec(lambda song, artists, **kw: None, name="songstats"),
        _make_spec(
            lambda song, artists, **kw: (_ for _ in ()).throw(ValueError("nope")),
            name="genius",
        ),
    ]
    monkeypatch.setattr(orchestrator, "EXTRACTORS", fake_specs)
    # Browser-Kontext nicht starten, also Playwright komplett ausstubsen
    monkeypatch.setattr(orchestrator, "sync_playwright", _stub_playwright)
    # Importer und IPC-Layer aus dem Spiel nehmen
    monkeypatch.setattr(orchestrator, "_handoff_to_processor", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "_publish_now_playing", lambda *a, **kw: None)

    statuses = orchestrator.handle_new_track(
        {"id": "t1", "song": "A", "artists": ["X"]}, headless=True
    )
    assert statuses == {
        "tunebat": "ok",
        "songstats": "no_match",
        "genius": statuses["genius"],  # nur Praefix pruefen
    }
    assert statuses["genius"].startswith("fail: ValueError")


# DEF: Minimal-Stub fuer sync_playwright(), damit handle_new_track ohne Browser laeuft
class _StubPage:
    pass


class _StubContext:
    def new_page(self):
        return _StubPage()

    def close(self):
        pass


class _StubBrowser:
    def new_context(self):
        return _StubContext()

    def close(self):
        pass


class _StubChromium:
    def launch(self, headless=True):
        return _StubBrowser()


class _StubPW:
    chromium = _StubChromium()


class _StubPWCtx:
    def __enter__(self):
        return _StubPW()

    def __exit__(self, *exc):
        return False


def _stub_playwright():
    return _StubPWCtx()
