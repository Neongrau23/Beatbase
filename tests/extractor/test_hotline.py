"""Unit-Tests fuer den globalen Hotline-Bus."""

import threading

from beatbase.extractor.hotline import Hotline, bus


def test_set_and_get_returns_value():
    bus.set("spotify", "id", "abc")
    assert bus.get("spotify", "id") == "abc"


def test_get_missing_key_returns_scherzhaften_default():
    result = bus.get("spotify", "missing")
    assert "kein anschluss" in result


def test_get_missing_key_with_explicit_default_returns_none():
    assert bus.get("spotify", "missing", default=None) is None


def test_get_missing_source_returns_default():
    assert bus.get("nonexistent_source", "any_key", default=None) is None


def test_set_overwrites_existing_value():
    bus.set("spotify", "id", "first")
    bus.set("spotify", "id", "second")
    assert bus.get("spotify", "id") == "second"


def test_clear_removes_everything():
    bus.set("spotify", "id", "abc")
    bus.set("tunebat", "bpm", "120")
    bus.clear()
    assert bus.get("spotify", "id", default=None) is None
    assert bus.get("tunebat", "bpm", default=None) is None


def test_get_all_returns_full_storage():
    bus.set("spotify", "id", "abc")
    bus.set("tunebat", "bpm", "120")
    all_data = bus.get_all()
    assert all_data == {
        "spotify": {"id": "abc"},
        "tunebat": {"bpm": "120"},
    }


def test_get_all_after_clear_is_empty():
    bus.set("spotify", "id", "abc")
    bus.clear()
    assert bus.get_all() == {}


def test_multiple_sources_dont_interfere():
    bus.set("spotify", "name", "Song A")
    bus.set("tunebat", "name", "Song B")
    assert bus.get("spotify", "name") == "Song A"
    assert bus.get("tunebat", "name") == "Song B"


def test_can_store_any_value_type():
    bus.set("s", "list_val", [1, 2, 3])
    bus.set("s", "dict_val", {"nested": True})
    bus.set("s", "none_val", None)
    assert bus.get("s", "list_val") == [1, 2, 3]
    assert bus.get("s", "dict_val") == {"nested": True}
    assert bus.get("s", "none_val") is None


def test_get_all_returns_copy_not_reference():
    """get_all darf keine Referenz auf die interne Struktur leaken,
    sonst koennte ein paralleler Schreiber waehrend Iteration crashen.
    """
    bus.set("spotify", "id", "abc")
    snapshot = bus.get_all()
    snapshot["spotify"]["id"] = "manipuliert"
    snapshot["new_source"] = {"foo": "bar"}
    assert bus.get("spotify", "id") == "abc"
    assert bus.get("new_source", "foo", default=None) is None


def test_concurrent_set_does_not_lose_writes():
    """Mehrere Threads schreiben unter unterschiedlichen Source-Keys —
    am Ende muessen alle Werte vorhanden sein.
    """
    local_bus = Hotline()
    iterations = 200
    thread_count = 4

    def writer(source: str) -> None:
        for i in range(iterations):
            local_bus.set(source, f"key{i}", i)

    threads = [
        threading.Thread(target=writer, args=(f"src{n}",)) for n in range(thread_count)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snapshot = local_bus.get_all()
    assert len(snapshot) == thread_count
    for n in range(thread_count):
        assert len(snapshot[f"src{n}"]) == iterations
        assert snapshot[f"src{n}"][f"key{iterations - 1}"] == iterations - 1


def test_concurrent_read_during_write_is_safe():
    """Reader-Threads duerfen waehrend paralleler Writes nicht crashen
    (z. B. ``RuntimeError: dictionary changed size during iteration``).
    """
    local_bus = Hotline()
    stop = threading.Event()
    errors: list[Exception] = []

    def writer() -> None:
        i = 0
        while not stop.is_set():
            local_bus.set("src", f"key{i}", i)
            i += 1

    def reader() -> None:
        try:
            while not stop.is_set():
                snap = local_bus.get_all()
                # Iterieren — soll niemals crashen, auch wenn writer parallel arbeitet.
                for _src, data in snap.items():
                    for _k, _v in data.items():
                        pass
        except Exception as e:
            errors.append(e)

    writers = [threading.Thread(target=writer) for _ in range(2)]
    readers = [threading.Thread(target=reader) for _ in range(2)]
    for t in writers + readers:
        t.start()

    threading.Event().wait(0.3)
    stop.set()
    for t in writers + readers:
        t.join()

    assert not errors, f"Reader-Threads sind gecrashed: {errors}"
