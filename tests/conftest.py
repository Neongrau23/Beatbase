"""Globale Pytest-Fixtures.

Wichtigste Aufgabe: Die Hotline ist ein globaler Singleton — jeder Test
bekommt einen frisch geleerten Bus, damit Tests sich nicht gegenseitig
beeinflussen.
"""

from pathlib import Path

import pytest

from beatbase.extractor.hotline import bus


@pytest.fixture(autouse=True)
def _clear_bus():
    """Setzt die Hotline vor und nach jedem Test zurueck."""
    bus.clear()
    yield
    bus.clear()


@pytest.fixture
def fixtures_dir() -> Path:
    """Wurzel des Fixture-Verzeichnisses (HTML-Dumps etc.)."""
    return Path(__file__).parent / "fixtures"
