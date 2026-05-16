"""SQLite-Speicher fuer Tunebat-Suchergebnisse."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/tunebat_searches.db")


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
            info_url TEXT,
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

    conn = _get_connection()
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
            r.get("infoUrl"),
            r.get("spotifyUrl"),
            r.get("songstatsUrl"),
            now,
        )
        for r in results
    ]

    conn.executemany(
        """INSERT INTO search_results
           (search_term, title, artists, key, bpm, camelot, popularity,
            image_url, info_url, spotify_url, songstats_url, searched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()
