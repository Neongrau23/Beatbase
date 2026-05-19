"""Paralleler Batch-Pfad mit 2-Phasen-Pipeline.

Alternative zu ``orchestrator.handle_new_track`` fuer den Batch-Modus.
Tunebat laeuft zuerst solo, damit der ``songstats_url``-Direktlink (siehe
``EXTRACTORS[songstats].direct_url_from``) in der Hotline landet, bevor
Songstats startet. Danach laufen Songstats, Genius und SongBPM parallel.

Zwei Modi:

- **Ohne Pool** (Default): jeder Aufruf oeffnet seinen eigenen Browser
  (``_run_extractor`` mit ``page=None``). Wird vom Standalone-Aufruf und
  als Fallback genutzt.
- **Mit Pool** (``handle_new_track_parallel(track, headless, pool=...)``):
  Die Browser bleiben ueber den ganzen Batch-Lauf offen, jeder Track
  wird nur an die existierenden Worker dispatcht. Siehe
  ``browser_pool.BrowserPool``.

Sammelstelle: Erst wenn alle Phase-2-Futures fertig sind, baut das
Callcenter die Summary und uebergibt sie an den Processor — identisch
zum sequenziellen Pfad.

In-Process-Retry: Liefert ein Extraktor ``"fail: ..."``, wird er einmal
nach ``BATCH_RETRY_DELAY_SECONDS`` erneut versucht, bevor der Status
persistiert wird. ``"no_match"`` (definitive Antwort) wird nicht retried.
Beim Pool-Pfad uebernimmt der Worker den Retry intern.
"""

import time
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from typing import TYPE_CHECKING, Optional

from beatbase.extractor.callcenter import get_summary_json
from beatbase.extractor.hotline import bus
from beatbase.extractor.orchestrator import (
    EXTRACTORS,
    ExtractorSpec,
    _handoff_to_processor,
    _publish_now_playing,
    _push_spotify,
    _run_extractor,
)
from beatbase.shared.config import BATCH_RETRY_DELAY_SECONDS, WATCHER_HEADLESS
from beatbase.shared.utils.log import log_status

if TYPE_CHECKING:
    from beatbase.extractor.browser_pool import BrowserPool


# DEF: Ein Extraktor mit einmaligem Retry bei "fail:"
def _run_extractor_with_retry(spec: ExtractorSpec, track: dict, headless: bool) -> str:
    """Wrappt ``_run_extractor`` und retried genau einmal bei ``"fail: ..."``.

    ``page=None`` wird durchgereicht — jede ``search_on_*``-Funktion oeffnet
    in dem Fall ihren eigenen Playwright-Kontext (selber Mechanismus wie bei
    den Standalone-CLI-Aufrufen).
    """
    status = _run_extractor(spec, track, page=None, headless=headless)
    if status.startswith("fail:"):
        log_status(
            f"♻️  {spec.label} retry in {BATCH_RETRY_DELAY_SECONDS:.0f}s nach: {status}"
        )
        time.sleep(BATCH_RETRY_DELAY_SECONDS)
        status = _run_extractor(spec, track, page=None, headless=headless)
    return status


# DEF: Phase 1 (Tunebat solo) — gemeinsamer Helper fuer Pool- und Non-Pool-Pfad
def _run_phase1(
    track: dict, headless: bool, pool: Optional["BrowserPool"]
) -> dict[str, str]:
    statuses: dict[str, str] = {}
    phase1 = [s for s in EXTRACTORS if s.name == "tunebat" and s.enabled]
    for spec in phase1:
        log_status(f"\n--- Phase 1: {spec.label} ---")
        if pool is not None and pool.has(spec.name):
            statuses[spec.name] = pool.submit(spec.name, track).result()
        else:
            statuses[spec.name] = _run_extractor_with_retry(spec, track, headless)
    return statuses


# DEF: Phase 2 (Songstats + Genius + SongBPM parallel) — gemeinsamer Helper
def _run_phase2(
    track: dict, headless: bool, pool: Optional["BrowserPool"]
) -> dict[str, str]:
    statuses: dict[str, str] = {}
    phase2 = [s for s in EXTRACTORS if s.name != "tunebat" and s.enabled]
    if not phase2:
        return statuses

    log_status(
        f"\n--- Phase 2: {', '.join(s.label for s in phase2)} parallel ---"
    )

    if pool is not None and all(pool.has(s.name) for s in phase2):
        # Pool-Pfad: Futures direkt vom Pool, kein eigener Executor noetig.
        future_to_name = {pool.submit(spec.name, track): spec.name for spec in phase2}
        wait(future_to_name, return_when=ALL_COMPLETED)
        for fut, name in future_to_name.items():
            try:
                statuses[name] = fut.result()
            except Exception as e:
                statuses[name] = f"fail: {type(e).__name__}: {e}"
        return statuses

    # Non-Pool-Pfad: lokaler ThreadPoolExecutor, jeder Worker oeffnet seinen
    # eigenen Browser (entspricht dem urspruenglichen Parallel-Verhalten).
    with ThreadPoolExecutor(
        max_workers=len(phase2), thread_name_prefix="beatbase-extractor"
    ) as executor:
        future_to_name = {
            executor.submit(_run_extractor_with_retry, spec, track, headless): spec.name
            for spec in phase2
        }
        wait(future_to_name, return_when=ALL_COMPLETED)
        for fut, name in future_to_name.items():
            try:
                statuses[name] = fut.result()
            except Exception as e:
                statuses[name] = f"fail: {type(e).__name__}: {e}"
    return statuses


# DEF: Verarbeitet einen Track parallel (Batch-Pfad)
def handle_new_track_parallel(
    track: dict,
    headless: bool = WATCHER_HEADLESS,
    pool: Optional["BrowserPool"] = None,
) -> dict[str, str]:
    """Reset Hotline, IPC schreiben, 2-Phasen-Pipeline ausfuehren, Summary uebergeben.

    Phase 1: Tunebat solo (synchron). Setzt ``songstats_url`` fuer die
    Cross-Extractor-Optimierung in den Bus.

    Phase 2: Songstats, Genius, SongBPM parallel.

    Wenn ``pool`` gesetzt ist, werden Tasks an die persistenten Worker im
    Pool dispatcht (siehe ``browser_pool.BrowserPool``). Ohne Pool oeffnet
    jede Quelle pro Track einen eigenen Browser.

    Sammelstelle: Erst nach Abschluss aller Phase-2-Futures wird das Summary
    gebaut und an den Processor uebergeben — kein Teil-Write.

    Returns:
        Dict ``{extractor_name: status}`` fuer jeden aktivierten Extraktor.
    """
    bus.clear()
    _publish_now_playing(track)
    _push_spotify(track)
    log_status(
        f"🎵 [parallel{'/pool' if pool else ''}] Neuer Song: {track.get('song')} "
        f"von {', '.join(track.get('artists', []))}"
    )

    statuses: dict[str, str] = {}
    statuses.update(_run_phase1(track, headless, pool))
    statuses.update(_run_phase2(track, headless, pool))

    summary_json = get_summary_json()
    log_status(" Zusammenfassung:")
    log_status(summary_json)

    spotify_id = track.get("id")
    if spotify_id:
        _handoff_to_processor(spotify_id, summary_json)

    return statuses
