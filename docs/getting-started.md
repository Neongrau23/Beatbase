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
cd Beatbase
```

### 2. Abhängigkeiten installieren

```powershell
uv sync
```

`uv sync` liest `pyproject.toml` und `uv.lock`, legt automatisch das virtuelle
Environment unter `.venv/` an und installiert alle Pakete deterministisch.

### 3. Playwright-Browser installieren

Alle Browser-Extraktoren (Tunebat, Songstats, Genius, SongBPM) nutzen
Playwright Chromium:

```powershell
uv run playwright install chromium
```

### 4. Spotify-Credentials

Lege eine Datei `.env` im Projektroot an:

```env
SPOTIPY_CLIENT_ID=dein_client_id
SPOTIPY_CLIENT_SECRET=dein_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback

# Optional: alternativer DB-Pfad für update_audio_features
# BEATBASE_DB_PATH=D:/eigener/pfad/spotify.db
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

Beim ersten Songwechsel öffnet sich **ein** Browser-Fenster (Playwright
Chromium), das von allen vier Extraktoren (Tunebat → Songstats → Genius →
SongBPM) der Reihe nach genutzt wird. Jeder Extraktor hat sein eigenes
**persistentes Profil** unter `.profiles/`:

- `.profiles/tunebat_profile/`
- `.profiles/songstats_profile/`
- `.profiles/genius_profile_playwright/`

Diese Verzeichnisse sind in `.gitignore`.

> ⚠️ **Profilverzeichnisse nicht löschen.** Sie speichern Cookies, Login-State
> und Anti-Bot-Reputation, damit du keine Captchas mehr lösen musst.

### Beispielausgabe

```
🚀 Beatbase Orchestrator wird gestartet... (PID: 12345)
👁️ Watcher aktiv. Polling-Intervall: 10s.
🎵 Neuer Song: Blinding Lights von The Weeknd

--- Tunebat ---
🔗 Suche auf Tunebat: 'Blinding Lights The Weeknd'
✅ Daten extrahiert.

--- Songstats ---
🔗 Nutze direkten Link: https://songstats.com/...?source=overview
📊 Extrahierte Details (Overview):

--- Genius ---
🔗 Suche auf Genius: Blinding Lights von The Weeknd
✅ Vollständige Daten (inkl. Lyrics) extrahiert.

--- SongBPM ---
🔗 Suche auf SongBPM: Blinding Lights The Weeknd

 Zusammenfassung:
{
    "meta": {"title": "Blinding Lights", "artist": "The Weeknd", ...},
    "music_theory": {"bpm": "171", "key": "F# minor", ...},
    ...
}
💾 Archiviert: data/json/abc123.json
```

### Watcher beenden

Drei Wege:

1. `Ctrl+C` im Watcher-Terminal — `KeyboardInterrupt` wird sauber gefangen.
2. Aus einem anderen Terminal:

   ```powershell
   uv run python -m beatbase --stop
   ```

   Liest die PID aus `.beatbase.pid` und schickt `SIGTERM`.
3. Notfall: Prozess via Task-Manager beenden und `.beatbase.pid` manuell löschen.

## Nächste Schritte

- [CLI-Referenz](cli.md) — Extraktoren einzeln aufrufen
- [Konfiguration](configuration.md) — Polling-Intervall, IPC-Mode, ENABLE-Toggles
- [Architektur](architecture.md) — Wie alles zusammenspielt
