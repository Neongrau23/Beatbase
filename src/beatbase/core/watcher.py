"""Zentraler Polling-Watcher.

Pollt Spotify in Intervallen, schreibt den aktuellen Song in den IPC-Layer
(Datei oder Env, je nach Config) und triggert bei Songwechsel die in `EXTRACTORS`
deklarierten Quellen. Browser werden pro Song frisch geöffnet und geschlossen.
"""

import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from beatbase.core.config import (
    ENABLE_GENIUS,
    ENABLE_SONGBPM,
    ENABLE_SONGSTATS,
    ENABLE_TUNEBAT,
    JSON_EXPORT_DIR,
    POLLING_INTERVAL,
    WATCHER_HEADLESS,
)
from beatbase.core.hotline import bus
from beatbase.genius.genius import search_on_genius
from beatbase.songbpm.songbpm import search_on_songbpm
from beatbase.songstats.songstats import search_on_songstats
from beatbase.spotify.spotify_current import get_current_spotify_track
from beatbase.tunebat.tunebat import search_on_tunebat
from beatbase.utils.callcenter import get_summary_json
from beatbase.utils.log import log_status
from beatbase.utils.now_playing import clear_now_playing, write_now_playing


# SECTION: PIPELINE - Deklarative Extraktor-Konfiguration
@dataclass(frozen=True)
class ExtractorSpec:
    """Beschreibt, wie ein Extraktor im Watcher-Loop ausgeführt wird.

    Attributes:
        name: Hotline-Source-Key (z. B. "tunebat"). Unter diesem Namen werden
            Resultate im `bus` abgelegt.
        label: Anzeigename für Log-Ausgaben.
        enabled: Wird die Quelle in diesem Lauf ausgeführt?
        search_fn: Die `search_on_*`-Funktion des Extraktors. Erwartet die
            Signatur `(song, artists, *, headless, page, **extras)`.
        store_under_data_key: Zusätzlich `bus.set(name, "data", result)` aufrufen.
            Wird vom Callcenter für komplexe Strukturen (Lyrics, SongBPM-Block) genutzt.
        direct_url_from: Optional `(source, key)` im Bus, dessen Wert als
            `direct_url`-Kwarg an `search_fn` durchgereicht wird. Ermöglicht
            Cross-Extractor-Optimierung (z. B. Tunebat → Songstats).
    """

    name: str
    label: str
    enabled: bool
    search_fn: Callable[..., dict | None]
    store_under_data_key: bool = False
    direct_url_from: tuple[str, str] | None = None


# CONFIG: Pipeline-Definition - Reihenfolge ist signifikant.
# Tunebat zuerst, weil es ggf. einen Songstats-Direktlink liefert.
EXTRACTORS: list[ExtractorSpec] = [
    ExtractorSpec(
        name="tunebat",
        label="Tunebat",
        enabled=ENABLE_TUNEBAT,
        search_fn=search_on_tunebat,
    ),
    ExtractorSpec(
        name="songstats",
        label="Songstats",
        enabled=ENABLE_SONGSTATS,
        search_fn=search_on_songstats,
        direct_url_from=("tunebat", "songstats_url"),
    ),
    ExtractorSpec(
        name="genius",
        label="Genius",
        enabled=ENABLE_GENIUS,
        search_fn=search_on_genius,
        store_under_data_key=True,
    ),
    ExtractorSpec(
        name="songbpm",
        label="SongBPM",
        enabled=ENABLE_SONGBPM,
        search_fn=search_on_songbpm,
        store_under_data_key=True,
    ),
]


# DEF: Speichert die Zusammenfassung in eine Datei
def _archive_summary(track_id: str, summary_json: str) -> None:
    """Speichert die Master-JSON im Archivordner."""
    if not os.path.exists(JSON_EXPORT_DIR):
        os.makedirs(JSON_EXPORT_DIR, exist_ok=True)

    file_path = os.path.join(JSON_EXPORT_DIR, f"{track_id}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(summary_json)
        log_status(f"💾 Archiviert: {file_path}")
    except Exception as e:
        log_status(f"❌ Archivierungs-Fehler: {e}")


# DEF: Aktualisiert den IPC-Layer mit dem aktuellen Track
def _publish_now_playing(track: dict) -> None:
    """Schreibt Song und Artist strukturiert in den IPC-Layer."""
    write_now_playing(track.get("song"), track.get("artists", []))


# DEF: Befüllt die Hotline mit Spotify-Rohdaten
def _push_spotify(track: dict) -> None:
    bus.set("spotify", "id", track.get("id"))
    bus.set("spotify", "name", track.get("song"))
    bus.set("spotify", "artists", track.get("artists"))
    bus.set("spotify", "isrc", track.get("isrc"))
    bus.set("spotify", "release_date", track.get("release_date"))
    bus.set("spotify", "url", track.get("spotify_url"))


# DEF: Führt einen einzelnen Extraktor mit Fehler-Isolation aus
def _run_extractor(spec: ExtractorSpec, track: dict, page, headless: bool) -> None:
    """Führt `spec.search_fn` aus und legt das Ergebnis im Bus ab.

    Exceptions werden gefangen, damit ein Crash eines Extraktors die Pipeline
    nicht stoppt — die folgenden Extraktoren laufen weiter.
    """
    log_status(f"\n--- {spec.label} ---")
    try:
        kwargs: dict = {"headless": headless, "page": page}
        if spec.direct_url_from:
            # WHY: explizit default=None — der Hotline-Default ist ein String,
            # der sonst als (fehlerhafte) URL durchgereicht würde.
            kwargs["direct_url"] = bus.get(*spec.direct_url_from, default=None)

        result = spec.search_fn(
            track.get("song"),
            list(track.get("artists", [])),
            **kwargs,
        )
        if not result:
            return

        if spec.store_under_data_key:
            bus.set(spec.name, "data", result)
        for k, v in result.items():
            bus.set(spec.name, k, v)
    except Exception as e:
        log_status(f"❌ {spec.label}-Fehler: {e}")


# DEF: Verarbeitet einen erkannten Songwechsel
def _handle_new_track(track: dict, headless: bool = WATCHER_HEADLESS) -> None:
    """Reset Hotline, IPC schreiben, alle aktivierten Extraktoren ausführen, Summary ausgeben."""
    bus.clear()
    _publish_now_playing(track)
    _push_spotify(track)
    log_status(f"🎵 Neuer Song: {track.get('song')} von {', '.join(track.get('artists', []))}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            for spec in EXTRACTORS:
                if spec.enabled:
                    _run_extractor(spec, track, page, headless)
        finally:
            context.close()
            browser.close()

    summary_json = get_summary_json()
    log_status(" Zusammenfassung:")
    log_status(summary_json)

    # Archivierung der Daten pro Song
    spotify_id = track.get("id")
    if spotify_id:
        _archive_summary(spotify_id, summary_json)


# DEF: Haupt-Loop
def run_watcher(headless: bool | None = None) -> None:
    """ENTRY: Endlos-Loop. Pollt Spotify und triggert Extraktoren bei Songwechsel."""
    last_track_id: str | None = None

    # Nutze headless-Parameter falls gegeben, sonst Config-Default
    active_headless = headless if headless is not None else WATCHER_HEADLESS

    log_status(f"👁️ Watcher aktiv. Polling-Intervall: {POLLING_INTERVAL}s.")
    if active_headless:
        log_status("🕶️ Headless-Modus aktiviert.")

    while True:
        try:
            track = get_current_spotify_track()

            if track is None:
                if last_track_id is not None:
                    log_status("⏸️ Kein aktiver Song.")
                    clear_now_playing()
                    last_track_id = None
            else:
                current_id = track.get("id")
                if current_id and current_id != last_track_id:
                    _handle_new_track(track, headless=active_headless)
                    last_track_id = current_id

            time.sleep(POLLING_INTERVAL)

        except KeyboardInterrupt:
            log_status("\n👋 Watcher beendet.")
            break
        except Exception as e:
            log_status(f"⚠️ Fehler im Watcher-Loop: {e}")
            time.sleep(POLLING_INTERVAL)
