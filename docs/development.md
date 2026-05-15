# Entwicklung

Wegweiser für Beitragende und für dich selbst in sechs Monaten.

## Setup

Identisch zum [Getting Started](getting-started.md). Zusätzlich für die
Entwicklung empfohlen:

- VS Code mit Python-Extension
- `ruff`-Extension für Inline-Lint-Hints
- Ein zweiter Spotify-Account zum Testen, damit du nicht versehentlich
  während des Codings den Watcher mit deinem normalen Hörverhalten triggerst

## Coding-Konventionen

### Sprache

- **Antworten und Doku auf Deutsch.** Auch Code-Kommentare können deutsch
  sein, müssen aber nicht.
- **Code, Dateinamen, CLI-Befehle, Funktionsnamen: Englisch.**

### Type Hints

Type Hints überall — Funktionssignaturen, Rückgabetypen, ggf. `dict[str, Any]`
bei generischen Bus-Operationen.

### Docstrings

Google-Style. Beispiel:

```python
def calculate_validation_score(found_text: str, target_string: str, artists: list[str]) -> float:
    """Bewertet, wie gut ein Suchergebnis zum gesuchten Song passt.

    Args:
        found_text: Der Text des gefundenen Suchergebnisses.
        target_string: Der zusammengesetzte Zielstring (Titel + Künstler).
        artists: Liste der erwarteten Künstler.

    Returns:
        Ein Float-Score, wobei höhere Werte einen besseren Match bedeuten.
    """
```

### Marker-Kommentare (für VS Code Minimap)

Beatbase nutzt eigene Marker, die in der VS Code Minimap und Outline-View
sichtbar sind:

| Marker | Zweck |
|--------|-------|
| `# DEF: Kurztext` | Wichtige Funktionsdefinition (max ~40 Zeichen) |
| `# SECTION:` | Logische Sektion innerhalb eines Moduls |
| `# ENTRY:` | Einstiegspunkt einer CLI / eines Skripts |
| `# CONFIG:` | Konfigurations-Block |
| `# BRIDGE:` | Verbindungspunkt zwischen Modulen |
| `# STATE:` | State-Initialisierung |
| `# WHY:` | Erklärung einer überraschenden Designentscheidung |
| `# HELP:` | Hilfsfunktion / interner Helper |
| `# MARK:` | Sub-Sektion (vor allem in `extractor.py`) |

Beispiel:

```python
# DEF: Befüllt die Hotline mit Spotify-Rohdaten
def _push_spotify(track: dict) -> None:
    ...
```

### Pfade

`pathlib.Path` bevorzugen, wo möglich. Bestandscode nutzt teilweise noch
`os.path` — beim Editieren nicht zwingend migrieren, aber neuer Code soll
`Path` verwenden.

### Strings

f-Strings (kein `%`-Formatting, kein `.format`).

### Exceptions

Spezifische Exceptions fangen, **kein nacktes `except:`**. Die Ausnahme
sind die Watcher-Try-Blöcke um die Extraktoren — dort ist `except Exception
as e` bewusst breit, damit ein Scraper-Crash den Loop nicht killt.

### Logging

`print()` ausschließlich für:
- CLI-Output, der bewusst nach stdout soll
- JSON-Ausgaben

Status-Meldungen gehören nach stderr:

```python
from beatbase.utils.log import log_status
log_status("🎵 Neuer Song erkannt")
```

So bleibt stdout pipe-bar:

```powershell
uv run python -m beatbase.songstats.songstats --song X --artist Y | jq .
```

### Line-Length

100 Zeichen (siehe `pyproject.toml`).

## Linting

```powershell
uv run ruff check .
```

Auto-Fix:

```powershell
uv run ruff check . --fix
```

Konfiguration in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

## Tests

Aktuell **keine Test-Suite**. `tests/` ist leer. Empfehlung:

- Tests spiegeln die `src/`-Struktur:
  `tests/songstats/test_validator.py` testet `src/beatbase/songstats/validator.py`.
- Pytest verwenden (`uv add --dev pytest`).
- Browser-Extraktoren mit Cassette-Pattern (z. B.
  [`vcrpy`](https://vcrpy.readthedocs.io/) oder gespeicherte HTML-Fixtures
  unter `tests/fixtures/`) — keine echten Live-Calls in CI.
- Bus / Callcenter sind unit-test-freundlich (`bus.clear()` vor jedem Test).

## Erweiterung

### Neue Datenquelle hinzufügen

1. Modul-Verzeichnis anlegen: `src/beatbase/lastfm/`.
2. Public-Entry schreiben:
   ```python
   def search_on_lastfm(song: str, artists: list[str]) -> dict:
       ...
   ```
3. Im Watcher (`core/watcher.py`) parallel zu `_run_songstats` einen
   `_run_lastfm` einbauen. Rohdaten in den Bus:
   ```python
   for k, v in result.items():
       bus.set("lastfm", k, v)
   ```
4. Falls Felder ins Summary einfließen sollen, `utils/callcenter.py`
   ergänzen.
5. CLI-Modul für Standalone-Aufruf inklusive IPC-Fallback bauen.

### Neues Audio-Feature aus Songstats

Songstats fügt von Zeit zu Zeit neue Felder zum Spider-Chart hinzu. Die
Liste in `scraper/metrics.py::results` updaten — sonst gehen Werte aus
überlappenden Null-Punkten verloren.

### Neuen Tooltip-Format-Fall

Im `metrics.py`-Parser sind drei Fälle abgedeckt: Prozent (`%`),
Dezibel (`DB`), und Fallback-Zahl. Bei neuen Einheiten dort ergänzen,
nicht im Aufrufer.

## Git-Hinweise

- `.spotify_cache`, `now_playing.txt`, `songstats_profile/`,
  `genius_profile_selenium/`, `.env`, `.venv/` sind in `.gitignore` —
  vor dem Commit prüfen, dass sie nicht versehentlich versioniert werden.
- Browser-Profile sind groß (>100 MB) — niemals committen.