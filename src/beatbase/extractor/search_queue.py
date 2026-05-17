"""SQLite-Tracking-Tabelle fuer den Batch-Modus.

Eine Zeile pro Track, eine Statusspalte pro Quelle. Werte:

- ``NULL`` ........ noch nicht versucht
- ``"ok"`` ........ Treffer gefunden
- ``"no_match"`` .. Quelle sauber gelaufen, aber kein Treffer (kein Retry)
- ``"fail: <msg>"`` Exception beim Scrapen (wird durch ``reset_fails`` retryebar)

Die DB lebt unter ``data/search_queue.db`` (ueber ``shared.config`` konfigurierbar)
und ist unabhaengig von ``data/songs.db`` und der externen Beatbase-DB. Sie ist
reines Audit/ToDo, keine Summary-Persistenz.
"""

import hashlib
import sqlite3
from datetime import datetime, timezone

from beatbase.shared.config import SEARCH_QUEUE_DB_PATH as DB_PATH

# SECTION: CONST - Reihenfolge entspricht der Pipeline im Orchestrator
SOURCES: tuple[str, ...] = ("tunebat", "songstats", "genius", "songbpm")


# DEF: SQLite-Connection mit Schema-Garantie
def _connect() -> sqlite3.Connection:
    """Oeffnet eine Verbindung und legt Tabelle/Index an, falls noetig."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_queue (
            track_id TEXT PRIMARY KEY,
            song TEXT NOT NULL,
            artist TEXT NOT NULL,
            isrc TEXT,
            release_date TEXT,
            tunebat_status TEXT,
            songstats_status TEXT,
            genius_status TEXT,
            songbpm_status TEXT,
            queued_at TEXT NOT NULL,
            last_attempt_at TEXT,
            attempts INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending
            ON search_queue (tunebat_status, songstats_status,
                             genius_status, songbpm_status)
    """)
    conn.commit()
    return conn


# DEF: 22-stellige Hash-ID fuer Tracks ohne Spotify-ID
def generate_id(song: str, artist: str) -> str:
    """Deterministischer Hash, gleich lang wie Spotify-Track-IDs (22 Zeichen)."""
    return hashlib.md5(f"{song}|{artist}".encode("utf-8")).hexdigest()[:22]


# DEF: Tracks einfuegen (idempotent)
def enqueue(tracks: list[dict]) -> int:
    """Fuegt Tracks hinzu. Bei Konflikt (gleiche ``track_id``) ignoriert.

    Args:
        tracks: Liste von Dicts mit Keys ``id``, ``song``, ``artist``,
            optional ``isrc`` und ``release_date``.

    Returns:
        Anzahl tatsaechlich neu eingefuegter Zeilen.
    """
    if not tracks:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM search_queue").fetchone()[0]
        conn.executemany(
            """INSERT OR IGNORE INTO search_queue
               (track_id, song, artist, isrc, release_date, queued_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    t["id"],
                    t["song"],
                    t["artist"],
                    t.get("isrc"),
                    t.get("release_date"),
                    now,
                )
                for t in tracks
            ],
        )
        after = conn.execute("SELECT COUNT(*) FROM search_queue").fetchone()[0]
    return after - before


# DEF: Liefert alle Tracks mit mindestens einer offenen Quelle
def fetch_pending(limit: int | None = None) -> list[dict]:
    """Tracks, bei denen noch mindestens eine Status-Spalte ``NULL`` ist.

    ``no_match`` und ``ok`` zaehlen als terminal und werden uebersprungen.
    """
    sql = (
        "SELECT track_id, song, artist, isrc, release_date,"
        " tunebat_status, songstats_status, genius_status, songbpm_status "
        "FROM search_queue "
        "WHERE tunebat_status IS NULL OR songstats_status IS NULL "
        "   OR genius_status IS NULL OR songbpm_status IS NULL "
        "ORDER BY queued_at"
    )
    params: tuple = ()
    if limit:
        sql += " LIMIT ?"
        params = (int(limit),)
    cols = (
        "track_id",
        "song",
        "artist",
        "isrc",
        "release_date",
        "tunebat_status",
        "songstats_status",
        "genius_status",
        "songbpm_status",
    )
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(zip(cols, row)) for row in rows]


# DEF: Status pro Quelle zurueckschreiben + attempts++
def update_statuses(track_id: str, statuses: dict[str, str]) -> None:
    """Schreibt Status pro Quelle. Unbekannte Quellen werden ignoriert."""
    valid = {k: v for k, v in statuses.items() if k in SOURCES}
    if not valid:
        return
    now = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{src}_status = ?" for src in valid)
    params = list(valid.values()) + [now, track_id]
    with _connect() as conn:
        conn.execute(
            f"UPDATE search_queue SET {set_clause}, last_attempt_at = ?, "
            f"attempts = attempts + 1 WHERE track_id = ?",
            params,
        )


# DEF: 'fail:...'-Statuus auf NULL zuruecksetzen (Retry-Vorbereitung)
def reset_fails(source: str | None = None) -> int:
    """Setzt ``fail:%``-Eintraege auf ``NULL``. ``no_match`` bleibt.

    Args:
        source: Wenn gesetzt, nur diese Quelle. Sonst alle.

    Returns:
        Anzahl zurueckgesetzter Zeilen (Summe ueber alle Quellen).
    """
    if source is not None and source not in SOURCES:
        raise ValueError(f"Unbekannte Quelle: {source}")
    sources = [source] if source else list(SOURCES)
    total = 0
    with _connect() as conn:
        for src in sources:
            cur = conn.execute(
                f"UPDATE search_queue SET {src}_status = NULL "
                f"WHERE {src}_status LIKE 'fail:%'"
            )
            total += cur.rowcount
    return total


# DEF: Kompakte Statistik fuer den 'batch status'-Befehl
def status_summary() -> dict:
    """Pro Quelle: Anzahl ``ok``, ``no_match``, ``fail``, ``pending``."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM search_queue").fetchone()[0]
        result: dict = {"total": total, "sources": {}}
        for src in SOURCES:
            counts = {
                "ok": conn.execute(
                    f"SELECT COUNT(*) FROM search_queue WHERE {src}_status = 'ok'"
                ).fetchone()[0],
                "no_match": conn.execute(
                    f"SELECT COUNT(*) FROM search_queue WHERE {src}_status = 'no_match'"
                ).fetchone()[0],
                "fail": conn.execute(
                    f"SELECT COUNT(*) FROM search_queue WHERE {src}_status LIKE 'fail:%'"
                ).fetchone()[0],
                "pending": conn.execute(
                    f"SELECT COUNT(*) FROM search_queue WHERE {src}_status IS NULL"
                ).fetchone()[0],
            }
            result["sources"][src] = counts
    return result
