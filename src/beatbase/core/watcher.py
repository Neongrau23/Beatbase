"""Zentraler Polling-Watcher.

Pollt Spotify in Intervallen, schreibt den aktuellen Song in den IPC-Layer
(Datei oder Env, je nach Config) und triggert bei Songwechsel die Extraktoren
(Songstats, Genius). Browser werden pro Song frisch geöffnet und geschlossen.
"""

import os
import time

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


# DEF: Songstats-Schritt mit Fehler-Isolation
def _run_songstats(track: dict, headless: bool = WATCHER_HEADLESS, page=None, direct_url: str | None = None) -> None:
    log_status("\n--- Songstats ---")
    try:
        result = search_on_songstats(
            track.get("song"),
            list(track.get("artists", [])),
            headless=headless,
            page=page,
            direct_url=direct_url,
        )
        if result:
            for k, v in result.items():
                bus.set("songstats", k, v)
    except Exception as e:
        log_status(f"❌ Songstats-Fehler: {e}")


# DEF: Genius-Schritt mit Fehler-Isolation
def _run_genius(track: dict, headless: bool = WATCHER_HEADLESS, page=None) -> None:
    log_status("\n--- Genius ---")
    try:
        result = search_on_genius(
            track.get("song"),
            list(track.get("artists", [])),
            headless=headless,
            page=page,
        )
        if result:
            bus.set("genius", "data", result)
            # Legacy-Support für Einzelfelder (falls noch woanders genutzt)
            for k, v in result.items():
                bus.set("genius", k, v)
    except Exception as e:
        log_status(f"❌ Genius-Fehler: {e}")


# DEF: Tunebat-Schritt mit Fehler-Isolation
def _run_tunebat(track: dict, headless: bool = WATCHER_HEADLESS, page=None) -> None:
    log_status("\n--- Tunebat ---")
    try:
        result = search_on_tunebat(
            track.get("song"),
            list(track.get("artists", [])),
            headless=headless,
            page=page,
        )
        if result:
            for k, v in result.items():
                bus.set("tunebat", k, v)
    except Exception as e:
        log_status(f"❌ Tunebat-Fehler: {e}")


# DEF: SongBPM-Schritt mit Fehler-Isolation
def _run_songbpm(track: dict, headless: bool = WATCHER_HEADLESS, page=None) -> None:
    log_status("\n--- SongBPM ---")
    try:
        result = search_on_songbpm(
            track.get("song"),
            list(track.get("artists", [])),
            headless=headless,
            page=page,
        )
        if result:
            bus.set("songbpm", "data", result)
            for k, v in result.items():
                bus.set("songbpm", k, v)
    except Exception as e:
        log_status(f"❌ SongBPM-Fehler: {e}")


# DEF: Verarbeitet einen erkannten Songwechsel
def _handle_new_track(track: dict, headless: bool = WATCHER_HEADLESS) -> None:
    """Reset Hotline, IPC schreiben, alle Extraktoren laufen lassen, Summary ausgeben."""
    bus.clear()
    _publish_now_playing(track)
    _push_spotify(track)
    log_status(f"🎵 Neuer Song: {track.get('song')} von {', '.join(track.get('artists', []))}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            if ENABLE_TUNEBAT:
                _run_tunebat(track, headless=headless, page=page)
            if ENABLE_SONGSTATS:
                # Prüfen, ob Tunebat einen direkten Link gefunden hat
                direct_url = bus.get("tunebat", "songstats_url")
                _run_songstats(track, headless=headless, page=page, direct_url=direct_url)
            if ENABLE_GENIUS:
                _run_genius(track, headless=headless, page=page)
            if ENABLE_SONGBPM:
                _run_songbpm(track, headless=headless, page=page)
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
