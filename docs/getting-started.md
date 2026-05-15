# Getting Started

Diese Anleitung führt dich vom frischen Clone bis zum laufenden Watcher.

## Voraussetzungen

| Komponente | Version / Hinweis |
|------------|-------------------|
| Python | ≥ 3.11 |
| Paketmanager | [`uv`](https://github.com/astral-sh/uv) — kein `pip`, kein manuelles `venv` |
| Betriebssystem | Windows (IPC nutzt im `env`-Mode die Windows-User-Variable `NOW_PLAY`) |
| Spotify Developer Account | Für `SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET` |

> **Hinweis:** Der Default-IPC-Mode ist `file`, also funktioniert Beatbase
> grundsätzlich auch auf macOS / Linux. Lediglich der `env`-Mode setzt eine
> Windows-User-Umgebungsvariable über PowerShell-Subprozesse.

## Installation

### 1. Repository klonen

```powershell
git clone <repo-url>
cd .beatbase
```

### 2. Abhängigkeiten installieren

```powershell
uv sync
```

`uv sync` liest `pyproject.toml` und `uv.lock`, legt automatisch das virtuelle
Environment unter `.venv/` an und installiert alle Pakete deterministisch.

### 3. Browser-Binary installieren

Playwright braucht eine eigene Chromium-Installation:

```powershell
uv run playwright install chromium
```

Selenium nutzt das systemweite Chrome — stelle sicher, dass Google Chrome
installiert ist. Der passende `chromedriver` wird ab Selenium 4 automatisch
verwaltet (Selenium Manager).

### 4. Spotify-Credentials

Lege eine Datei `.env` im Projektroot an:

```env
SPOTIPY_CLIENT_ID=dein_client_id
SPOTIPY_CLIENT_SECRET=dein_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
```

Beide IDs erhältst du im [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
Trage die `Redirect URI` zusätzlich dort unter *Edit Settings* ein.

> Der Spotify-OAuth-Flow läuft beim ersten Aufruf interaktiv im Browser. Der
> Token wird in `src/beatbase/spotify/.spotify_cache` gespeichert.

## Erste Ausführung

### Watcher starten

```powershell
uv run python -m beatbase
```

Beim ersten Songwechsel öffnen sich kurz zwei Browserfenster (Playwright für
Songstats, Selenium für Genius) — beide haben **persistente Profile**
(`songstats_profile/`, `genius_profile_selenium/`) und sind in `.gitignore`.

> ⚠️ **Profilverzeichnisse nicht löschen.** Sie speichern Cookies und
> Login-State, damit du keine Captchas mehr lösen musst.

### Beispielausgabe

```
🚀 Beatbase Orchestrator wird gestartet...
👁️ Watcher aktiv. Polling-Intervall: 15s.
🎵 Neuer Song: Blinding Lights von The Weeknd

--- Songstats ---
🔍 Songstats-Suche: Blinding Lights von The Weeknd
  📊 Extrahierte Details:
  Audio Features
  -----------------------------------
    -> Energy                    : 0.73
    -> Danceability              : 0.51
    ...

--- Genius ---
🔗 Suche nach: Blinding Lights The Weeknd
✅ Vollständige Daten (inkl. Lyrics) extrahiert.

📋 Zusammenfassung:
  title: Blinding Lights
  isrc: USUG11904206
  release_date: 2019-11-29
  genius_url: https://genius.com/...
```

### Watcher beenden

`Ctrl+C` — der Loop fängt `KeyboardInterrupt` und beendet sauber.

## Nächste Schritte

- [CLI-Referenz](cli.md) — Extraktoren einzeln aufrufen
- [Konfiguration](configuration.md) — Polling-Intervall, IPC-Mode anpassen
- [Architektur](architecture.md) — Wie alles zusammenspielt
