"""Zentraler Polling-Watcher.

Pollt Spotify in Intervallen, schreibt den aktuellen Song in den IPC-Layer
(Datei oder Env, je nach Config) und triggert bei Songwechsel die in `EXTRACTORS`
deklarierten Quellen. Browser werden pro Song frisch geöffnet und geschlossen.

Nach jedem Song wird die fertige Summary in die Queue (data/queue/) geschrieben
und anschliessend synchron der Processor-Importer aufgerufen. Damit ist die
Naht zwischen Standort 1 (Beschaffung) und Standort 2 (Verarbeitung) im Code
real, ohne dass es einen zweiten Prozess braucht.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from beatbase.extractor.callcenter import get_summary_json
from beatbase.extractor.genius.genius import search_on_genius
from beatbase.extractor.hotline import bus
from beatbase.extractor.queue import write_to_queue
from beatbase.extractor.songbpm.songbpm import search_on_songbpm
from beatbase.extractor.songstats.songstats import search_on_songstats
from beatbase.extractor.spotify.spotify_current import get_current_spotify_track
from beatbase.extractor.tunebat.tunebat import search_on_tunebat
from beatbase.processor.importer import process_queue
from beatbase.shared.config import (
    ENABLE_GENIUS,
    ENABLE_SONGBPM,
    ENABLE_SONGSTATS,
    ENABLE_TUNEBAT,
    POLLING_INTERVAL,
    WATCHER_HEADLESS,
)
from beatbase.shared.now_playing import clear_now_playing, write_now_playing
from beatbase.shared.utils.log import log_status
from beatbase.shared.utils.playwright_errors import is_browser_closed_error


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


# DEF: Reicht die fertige Summary an Standort 2 weiter
def _handoff_to_processor(track_id: str, summary_json: str) -> None:
    """Legt die Summary in der Queue ab und triggert den Importer synchron.

    Der Importer kuemmert sich um:
    - songs_db (lokale flache SQLite)
    - external_db (Audio-Features in die uebergeordnete Beatbase-DB)
    - Archivierung nach data/json/
    """
    try:
        write_to_queue(track_id, summary_json)
        log_status(f"📤 In Queue: {track_id}.json")
        process_queue()
    except Exception as e:
        log_status(f"❌ Handoff-Fehler: {e}")


# DEF: Aktualisiert den IPC-Layer mit dem aktuellen Track
def _publish_now_playing(track: dict) -> None:
    song = track.get("song")
    if song is None:
        return
    write_now_playing(song, track.get("artists", []))


# DEF: Befüllt die Hotline mit Spotify-Rohdaten
def _push_spotify(track: dict) -> None:
    bus.set("spotify", "id", track.get("id"))
    bus.set("spotify", "name", track.get("song"))
    bus.set("spotify", "artists", track.get("artists"))
    bus.set("spotify", "album", track.get("album"))
    bus.set("spotify", "isrc", track.get("isrc"))
    bus.set("spotify", "release_date", track.get("release_date"))
    bus.set("spotify", "url", track.get("spotify_url"))


# DEF: Führt einen einzelnen Extraktor mit Fehler-Isolation aus
def _run_extractor(spec: ExtractorSpec, track: dict, page, headless: bool) -> str:
    """Führt `spec.search_fn` aus und legt das Ergebnis im Bus ab.

    Exceptions werden gefangen, damit ein Crash eines Extraktors die Pipeline
    nicht stoppt — die folgenden Extraktoren laufen weiter.

    Returns:
        "ok" bei Treffer, "no_match" bei leerem Ergebnis,
        "fail: <Klasse>: <msg>" bei Exception.
    """
    log_status(f"\n--- {spec.label} ---")
    try:
        kwargs: dict = {"headless": headless, "page": page, "album": track.get("album")}
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
            return "no_match"

        if spec.store_under_data_key:
            bus.set(spec.name, "data", result)
        for k, v in result.items():
            bus.set(spec.name, k, v)
        return "ok"
    except Exception as e:
        # WHY: Browser-Closed-Fehler durchbrechen — der Pool-Worker erkennt sie
        # und faehrt den Browser neu hoch + retried. Andere Exceptions sind
        # echte Scraper-Probleme, die als 'fail:' an die Statuszeile gehen.
        if is_browser_closed_error(e):
            raise
        log_status(f"❌ {spec.label}-Fehler: {e}")
        return f"fail: {type(e).__name__}: {e}"


# DEF: Verarbeitet einen erkannten Songwechsel
def handle_new_track(track: dict, headless: bool = WATCHER_HEADLESS) -> dict[str, str]:
    """Reset Hotline, IPC schreiben, alle aktivierten Extraktoren ausführen, Summary ausgeben.

    Returns:
        Dict ``{extractor_name: status}`` fuer jeden aktivierten Extraktor.
        Werte sind ``"ok"``, ``"no_match"`` oder ``"fail: <msg>"``.
        Der normale Spotify-Watcher ignoriert den Rueckgabewert; der Batch-Modus
        schreibt ihn in ``search_queue.db``.
    """
    bus.clear()
    _publish_now_playing(track)
    _push_spotify(track)
    log_status(f"🎵 Neuer Song: {track.get('song')} von {', '.join(track.get('artists', []))}")

    statuses: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            for spec in EXTRACTORS:
                if spec.enabled:
                    statuses[spec.name] = _run_extractor(spec, track, page, headless)
        finally:
            context.close()
            browser.close()

    summary_json = get_summary_json()
    log_status(" Zusammenfassung:")
    log_status(summary_json)

    # Uebergabe an Standort 2 (Queue + Importer)
    spotify_id = track.get("id")
    if spotify_id:
        _handoff_to_processor(spotify_id, summary_json)

    return statuses


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
                    handle_new_track(track, headless=active_headless)
                    last_track_id = current_id

            time.sleep(POLLING_INTERVAL)

        except KeyboardInterrupt:
            log_status("\n👋 Watcher beendet.")
            break
        except Exception as e:
            log_status(f"⚠️ Fehler im Watcher-Loop: {e}")
            time.sleep(POLLING_INTERVAL)
