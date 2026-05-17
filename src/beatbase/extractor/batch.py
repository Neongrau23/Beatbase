"""Batch-Modus: Verarbeitet Tracks aus ``data/search_queue.db`` ohne Spotify-Polling.

Aufrufpfade aus ``__main__.py``:

- ``add``     -> ``add_from_file(csv)``: CSV einlesen, Tracks in DB einfuegen.
- ``run``     -> ``run()``: alle Tracks mit offenen Statuus durch die Pipeline.
- ``retry``   -> ``retry()``: ``fail:%`` zuruecksetzen, dann ``run()``.
- ``status``  -> ``status()``: Zaehlung pro Quelle.

Die Pipeline selbst ist die gleiche wie im Spotify-Watcher (``handle_new_track``).
"""

import csv
from pathlib import Path

from beatbase.extractor import search_queue
from beatbase.extractor.orchestrator import handle_new_track
from beatbase.shared.utils.log import log_status


# DEF: CSV-Zeile in ein Track-Dict normalisieren
def _row_to_track(row: dict) -> dict | None:
    """Validiert eine CSV-Zeile und liefert ein Track-Dict (oder ``None``).

    Pflichtfelder: ``song`` und ``artist``. ``id`` ist optional und wird bei
    Bedarf via ``search_queue.generate_id`` aus song+artist gehasht.
    Mehrere Kuenstler werden in der CSV-Zelle mit ``;`` getrennt und im
    DB-Eintrag genauso belassen — der ``run``-Schritt splittet erst dort.
    """
    song = (row.get("song") or "").strip()
    artist = (row.get("artist") or "").strip()
    if not song or not artist:
        return None
    track_id = (row.get("id") or "").strip() or search_queue.generate_id(song, artist)
    return {
        "id": track_id,
        "song": song,
        "artist": artist,
        "isrc": (row.get("isrc") or "").strip() or None,
        "release_date": (row.get("release_date") or "").strip() or None,
    }


# DEF: CSV einlesen und in die search_queue stopfen
def add_from_file(path: Path) -> int:
    """Liest eine CSV (Header ``id,song,artist[,isrc,release_date]``) und enqueued.

    Returns:
        Anzahl tatsaechlich neu eingefuegter Tracks (Duplikate ignoriert).
    """
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    tracks = [t for t in (_row_to_track(r) for r in rows) if t]
    skipped = len(rows) - len(tracks)
    inserted = search_queue.enqueue(tracks)
    log_status(
        f"📥 {inserted}/{len(tracks)} neue Tracks in search_queue eingetragen"
        + (f" ({skipped} Zeile(n) ohne song/artist uebersprungen)" if skipped else "")
    )
    return inserted


# DEF: Pending-Tracks durch die Pipeline jagen
def run(headless: bool = False, limit: int | None = None) -> None:
    """Verarbeitet alle Tracks mit mindestens einer offenen Status-Spalte.

    Schreibt nach jedem Track den Status pro Quelle zurueck in die search_queue.
    Crashes in ``handle_new_track`` werden gefangen — der Track wird dann mit
    ``fail:`` fuer alle bisher unbestimmten Quellen markiert, damit der naechste
    ``retry`` ihn aufgreifen kann.
    """
    pending = search_queue.fetch_pending(limit=limit)
    log_status(f"📋 {len(pending)} Track(s) ausstehend")
    if not pending:
        return

    for idx, row in enumerate(pending, 1):
        artists = [a.strip() for a in row["artist"].split(";") if a.strip()]
        track = {
            "id": row["track_id"],
            "song": row["song"],
            "artists": artists,
            "isrc": row["isrc"],
            "release_date": row["release_date"],
            "spotify_url": None,
        }
        log_status(
            f"\n=== [{idx}/{len(pending)}] {track['song']} — {', '.join(artists)} ==="
        )
        try:
            statuses = handle_new_track(track, headless=headless)
        except Exception as e:
            log_status(f"❌ Track {track['id']} crashed: {e}")
            # WHY: nur die noch nicht terminalen Quellen als fail markieren — ein
            # vorher schon erfolgreicher 'ok' soll nicht ueberschrieben werden.
            statuses = {
                src: f"fail: {type(e).__name__}: {e}"
                for src in search_queue.SOURCES
                if row.get(f"{src}_status") is None
            }
        if statuses:
            search_queue.update_statuses(track["id"], statuses)


# DEF: Erst 'fail:%' zuruecksetzen, dann run()
def retry(source: str | None = None, headless: bool = False) -> None:
    """Macht ``fail:`` wieder pending und ruft direkt ``run`` auf.

    Args:
        source: Wenn gesetzt, nur diese Quelle zuruecksetzen.
        headless: An ``run`` durchgereicht.
    """
    count = search_queue.reset_fails(source)
    suffix = f" fuer Quelle '{source}'" if source else ""
    log_status(f"♻️  {count} Status-Eintrag(e) zurueckgesetzt{suffix}")
    run(headless=headless)


# DEF: Kompakte Tabelle pro Quelle ausgeben
def status() -> None:
    """Loggt eine Uebersicht ueber den Stand der search_queue."""
    summary = search_queue.status_summary()
    log_status(f"📊 Gesamt: {summary['total']} Track(s)")
    for src, counts in summary["sources"].items():
        log_status(
            f"   {src:<10} ok={counts['ok']:<5} no_match={counts['no_match']:<5} "
            f"fail={counts['fail']:<5} pending={counts['pending']:<5}"
        )
