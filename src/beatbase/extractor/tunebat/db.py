"""Append-only SQLite-Persistenz fuer rohe Tunebat-Suchergebnisse.

Jeder Aufruf von save_search_results() schreibt alle Treffer einer Suchanfrage
als separate Zeilen in die Tabelle search_results (data/tunebat_searches.db).
Eintraege werden niemals ueberschrieben – das ermoeglicht spaetere Analyse,
welche Suchbegriffe wie viele und welche Treffer geliefert haben.

Schema:  search_term | title | artists (JSON) | key | bpm | camelot |
         popularity | image_url | tunebat_url | spotify_url | songstats_url |
         searched_at (ISO-8601 UTC)

Index:   search_term fuer schnelle Abfragen nach Suchbegriff.
"""

import json
import sqlite3
from datetime import datetime, timezone

from beatbase.shared.config import TUNEBAT_SEARCHES_DB_PATH as DB_PATH


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_term TEXT NOT NULL,
            title TEXT,
            artists TEXT,
            key TEXT,
            bpm INTEGER,
            camelot TEXT,
            popularity INTEGER,
            image_url TEXT,
            tunebat_url TEXT,
            spotify_url TEXT,
            songstats_url TEXT,
            searched_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_term ON search_results (search_term)
    """)
    conn.commit()
    return conn


def save_search_results(search_term: str, results: list[dict]) -> None:
    """Speichert eine Liste geparster Suchergebnisse in die DB."""
    if not results:
        return

    now = datetime.now(timezone.utc).isoformat()

    rows = [
        (
            search_term,
            r.get("title"),
            json.dumps(r.get("artists", []), ensure_ascii=False),
            r.get("key"),
            r.get("bpm"),
            r.get("camelot"),
            r.get("popularity"),
            r.get("imageUrl"),
            r.get("tunebatUrl"),
            r.get("spotifyUrl"),
            r.get("songstatsUrl"),
            now,
        )
        for r in results
    ]

    with _get_connection() as conn:
        conn.executemany(
            """INSERT INTO search_results
               (search_term, title, artists, key, bpm, camelot, popularity,
                image_url, tunebat_url, spotify_url, songstats_url, searched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
