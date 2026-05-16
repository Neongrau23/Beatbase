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
sind die Try-Blöcke um Extraktoren in `_run_extractor` — dort ist
`except Exception` bewusst breit, damit ein Scraper-Crash die Pipeline
nicht killt.

### Return-Werte

`search_on_*`-Funktionen liefern **`dict | None`** — `None` bei Fehler oder
leerem Ergebnis. Keine `{}`-Sentinel zurückgeben (Verwirrungsfaktor mit echten
leeren Strukturen).

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
uv run python -m beatbase.tunebat.tunebat --song X --artist Y | jq .
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

[tool.ruff.lint]
select = ["E", "F", "I"]
```

## Tests

```powershell
uv run pytest                        # alle Tests (~0.4s)
uv run pytest tests/utils/           # nur ein Subtree
uv run pytest -k callcenter          # nach Namen filtern
uv run pytest -m "not integration"   # Integration-Tests ausschliessen
```

Konfig in `pyproject.toml` unter `[tool.pytest.ini_options]`:
- `testpaths = ["tests"]`
- `--import-mode=importlib` — erlaubt mehrere `test_*.py` mit gleichem
  basename in verschiedenen Subdirs ohne `__init__.py`.
- Marker `integration` fuer Browser-/Netz-Tests (aktuell nicht benutzt).

### Struktur

`tests/` spiegelt `src/beatbase/`:

```
tests/
├── conftest.py                          # autouse-Fixture cleart Hotline-Bus
├── fixtures/
│   ├── songstats/overview.html
│   ├── genius/song.html
│   └── songbpm/detail.html
├── core/test_hotline.py
├── utils/
│   ├── test_callcenter.py
│   ├── test_now_playing.py
│   ├── test_search_variations.py
│   └── test_validator.py
├── songstats/test_overview.py
├── genius/test_extractor.py
└── songbpm/test_extractor.py
```

### Was abgedeckt ist

- **Pure functions** (Hotline-Bus, Callcenter-Schema mit Source/FieldSpec/
  _pick/_join_list/_from_dict/_determine_release_date, generate_variations,
  extract_featured_artists, calculate_validation_score).
- **IPC-Layer file-backend** (JSON-Roundtrip, Sentinel, Legacy-Format,
  atomares Schreiben).
- **Extraktoren mit HTML-Fixtures** (`_extract_overview`,
  `extrahiere_song_details_json`, `extract_song_info` via
  monkeypatched `requests.get`).

### Was nicht abgedeckt ist

- Playwright-Pfade (`search_on_*`, `browser/navigator.py`,
  `browser/context.py`) — brauchen echte HTML-Dumps oder Playwright-Mocks.
- Watcher-Pipeline-Integration (`_handle_new_track`).
- `env`-Backend in `now_playing.py` (PowerShell-Subprozess).

### Neue Tests hinzufügen

- Tests spiegeln die `src/`-Struktur. Beispiel: `tests/utils/test_callcenter.py`
  testet `src/beatbase/utils/callcenter.py`.
- Bus / Callcenter sind unit-test-freundlich — die `_clear_bus`-Fixture in
  `conftest.py` setzt den globalen Singleton vor jedem Test zurueck.
- Fuer HTML-Fixtures: ein neues Minimal-HTML unter
  `tests/fixtures/<modul>/<name>.html` ablegen, dann via `fixtures_dir`-
  Fixture im Test laden.

## Erweiterung

### Neue Datenquelle hinzufügen

1. Modul-Verzeichnis anlegen: `src/beatbase/lastfm/`.
2. Submodul-Struktur (für Browser-Quellen): `browser/context.py`,
   `browser/navigator.py`, `scraper/extractor.py`.
3. Public-Entry schreiben:
   ```python
   def search_on_lastfm(
       song: str,
       artists: list[str],
       headless: bool = False,
       page=None,
   ) -> dict | None: ...
   ```
4. Im Watcher (`core/watcher.py`) eine `ExtractorSpec` zur `EXTRACTORS`-Liste
   hinzufügen — Reihenfolge beachten. Optional `ENABLE_LASTFM`-Toggle in
   `core/config.py`.
5. Falls Felder ins Master-Summary einfließen sollen, das entsprechende
   Schema-Dict in `utils/callcenter.py` ergänzen (z. B. neue `Source` in
   `MUSIC_THEORY` oder neuen Block).
6. CLI-Modul für Standalone-Aufruf inklusive IPC-Fallback bauen.

### Neue Felder ins Master-Schema

Das Master-Schema lebt in `utils/callcenter.py` als `META`,
`MUSIC_THEORY`, `LINKS`-Dicts. Felder dort ergänzen — kein anderer Code muss
sich ändern.

## Git-Hinweise

- `.spotify_cache`, `now_playing.txt`, `.beatbase.pid`, `.profiles/`, `.env`,
  `.venv/`, `data/` sind in `.gitignore` — vor dem Commit prüfen, dass sie
  nicht versehentlich versioniert werden.
- Browser-Profile sind groß (>100 MB) — niemals committen.
- Commit-Konvention: `type(scope): kurze beschreibung` auf Deutsch.
  Beispiele aus der History: `refactor(watcher): ...`,
  `fix(tunebat): ...`, `chore(gitignore): ...`.
