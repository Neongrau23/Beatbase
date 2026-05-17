"""Append-only SQLite-Persistenz fuer Genius-Artist-Songs.

Jeder Aufruf von ``save_artist_songs()`` schreibt die auf einer
Artist-Songs-Seite gefundenen Eintraege in die Tabelle ``songs``
(``data/genius.db``). Duplikate werden ueber den UNIQUE-Constraint auf
``genius_url`` automatisch ignoriert. Eintraege werden niemals geloescht
oder ueberschrieben — die DB waechst stetig.

Schema: song | artist | genius_url (PRIMARY KEY)
"""

import sqlite3

from beatbase.shared.config import GENIUS_DB_PATH as DB_PATH


# DEF: SQLite-Connection mit Schema-Garantie
def _connect() -> sqlite3.Connection:
    """Oeffnet eine Verbindung und legt Tabelle an, falls noetig."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            genius_url TEXT PRIMARY KEY,
            song TEXT NOT NULL,
            artist TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


# DEF: Schreibt eine Liste von Artist-Songs in die DB
def save_artist_songs(songs: list[dict]) -> int:
    """Fuegt Eintraege ein. Bei Konflikt auf ``genius_url`` ignoriert.

    Args:
        songs: Liste von Dicts wie aus ``extract_artist_songs`` zurueckgegeben.
            Erwartet ``title``, ``subtitle`` (== Artist) und ``url``.

    Returns:
        Anzahl tatsaechlich neu eingefuegter Zeilen.
    """
    rows = [
        (s["url"], s.get("title") or "", s.get("subtitle") or "")
        for s in songs
        if s.get("url") and s.get("title")
    ]
    if not rows:
        return 0

    with _connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO songs (genius_url, song, artist) VALUES (?, ?, ?)",
            rows,
        )
        after = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
    return after - before
