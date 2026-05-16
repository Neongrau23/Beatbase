"""Unit-Tests fuer den globalen Hotline-Bus."""

from beatbase.core.hotline import bus


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
