# Architektur & Konzepte

Kurzüberblick. Die vollständige Doku liegt in
[`docs/architecture.md`](docs/architecture.md).

## Hotline / Callcenter

Zweistufiger Datenfluss zur Quellenagnostischen Aggregation:

- **Hotline** (`core/hotline.py`) — globaler, unstrukturierter Key-Value-Bus.
  Jeder Extraktor wirft seine Rohdaten unter seinem Quellennamen rein.
- **Callcenter** (`utils/callcenter.py`) — deklaratives Schema (`META`,
  `MUSIC_THEORY`, `LINKS`). Pro Feld eine geordnete Source-Liste; die erste
  truthy Quelle gewinnt.

## Extraktoren

| Quelle | Modul | Technologie |
|--------|-------|-------------|
| Spotify | `spotify/` | `spotipy` + OAuth2 |
| Tunebat | `tunebat/` | Playwright + `playwright-stealth` |
| Songstats | `songstats/` | Playwright + BeautifulSoup |
| Genius | `genius/` | Playwright + BeautifulSoup |
| SongBPM | `songbpm/` | Playwright + BeautifulSoup |

Alle Browser-Extraktoren nutzen persistente Profile in `.profiles/`.

## Watcher

`core/watcher.py` ist der Orchestrator. Eine deklarative `EXTRACTORS`-Liste
beschreibt die Pipeline (Tunebat → Songstats → Genius → SongBPM).

Pro Songwechsel wird **ein** Playwright-Browser geöffnet und an alle
Extraktoren weitergegeben. Tunebat liefert dabei einen Direktlink, den
Songstats nutzt, um die eigene Suche zu überspringen.

## IPC-Layer

`utils/now_playing.py` — Datei- oder Env-basiert (`IPC_MODE`-Konstante).
Format: JSON mit `{"song": ..., "artists": [...]}`. Atomar geschrieben.

## Externe DB

Optional via `--track-id`-Flag in Songstats. Pfad: `BEATBASE_DB_PATH`
(Default `C:/workspace/beatbase/spotify.db`, via Env-Var überschreibbar).
Gehört nicht zum Repo.

Für Details siehe die Dokumentation unter [`docs/`](docs/).
