# 🎵 Beatbase

**Musik-Metadaten Aggregator** — Die Brücke zwischen Spotify, Songstats und Genius.

Beatbase erkennt automatisch den aktuell spielenden Track auf Spotify und sammelt parallel tiefgreifende Metadaten, Audio-Features, Lyrics und Credits. Es kombiniert offizielle API-Daten mit mächtigen Browser-Scrapern für eine vollständige musikalische Analyse.

---

## 🚀 Schnellstart

### 1. Voraussetzungen
- **Python** ≥ 3.11
- **Paketmanager:** [`uv`](https://github.com/astral-sh/uv)
- **Browser:** Google Chrome (für Selenium/Genius)

### 2. Installation
```powershell
# Abhängigkeiten installieren
uv sync

# Playwright Browser (für Songstats) installieren
uv run playwright install chromium
```

### 3. Konfiguration
Erstelle eine `.env`-Datei im Projektroot mit deinen Spotify-API-Zugangsdaten (Details unter [Getting Started](docs/getting-started.md)):
```env
SPOTIPY_CLIENT_ID=dein_id
SPOTIPY_CLIENT_SECRET=dein_secret
```

### 4. Watcher starten
```powershell
uv run python -m beatbase
```

---

## 🏗️ Funktionsweise & Architektur

Beatbase nutzt einen zentralen **Watcher**, der Spotify pollt. Bei einem Songwechsel werden die Extraktoren getriggert:

```
Spotify API ─┐
             ├─► Hotline (bus) ──► Callcenter ──► Strukturierte Song-Daten
Songstats ───┤
Genius ──────┘
```

- 🛰️ **Hotline:** Ein schema-freier Datenbus, der Rohdaten aller Quellen sammelt.
- ☎️ **Callcenter:** Aggregiert die Daten, löst Konflikte und erstellt eine saubere Zusammenfassung.
- 💾 **IPC-Layer:** Ermöglicht es den Extraktoren, auch standalone den aktuellen Song zu kennen.

---

## 📂 Dokumentation

Hier findest du alle Details zur Nutzung und Erweiterung von Beatbase:

### 📖 Grundlagen
- 🏁 **[Getting Started](docs/getting-started.md)** — Installation & Setup.
- ⚙️ **[Konfiguration](docs/configuration.md)** — Alle Stellschrauben (Polling, IPC, Pfade).
- 🛠️ **[CLI-Referenz](docs/cli.md)** — Modulaufrufe & Argumente.
- ❓ **[Troubleshooting](docs/troubleshooting.md)** — Lösungen für bekannte Probleme.

### 📐 System-Design
- 🏛️ **[Architektur](docs/architecture.md)** — Designentscheidungen & Datenfluss.
- 💻 **[Entwicklung](docs/development.md)** — Coding-Konventionen & Marker-Kommentare.

### 🧩 Module
- 🟢 **[Spotify](docs/modules/spotify.md)** — API-Extraktion.
- 📊 **[Songstats](docs/modules/songstats.md)** — Highcharts-Scraping & Audio-Features.
- 📝 **[Genius](docs/modules/genius.md)** — Lyrics & Credits via Selenium.
- 👁️ **[Watcher](docs/modules/watcher.md)** — Der Orchestrator-Loop.

---

## 🛠️ Entwicklung

Das Projekt nutzt **Ruff** für Linting und **uv** für das Dependency-Management.

```powershell
# Linter ausführen
uv run ruff check .

# Formatierung prüfen/fixen
uv run ruff check . --fix
```

Weitere Details findest du im **[Development Guide](docs/development.md)**.
