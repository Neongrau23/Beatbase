"""Schreibt Audio-Features in die uebergeordnete externe Beatbase-SQLite-DB.

Diese DB gehoert zu einem uebergeordneten System (Pfad in
``BEATBASE_DB_PATH``, default ``C:/workspace/beatbase/spotify.db``) und ist
unabhaengig von der lokalen ``data/songs.db``.
"""

import sqlite3

from beatbase.shared.config import BEATBASE_DB_PATH


# DEF: update_audio_features(track_id, features) -> None
def update_audio_features(track_id: str, features: dict) -> None:
    """Schreibt Audio-Features fuer einen Track in die externe Beatbase-DB.

    Erwartet das Summary-Format (kleinbuchstaben), z. B.::

        {"danceability": 0.7, "energy": 0.8, "happiness": 0.5, ...}

    ``happiness`` wird auf die ``valence``-Spalte gemappt (gleiches Konzept,
    verschiedene Namen in Songstats vs. Spotify-API).

    Args:
        track_id: Track-ID (Primary Key in ``tracks``).
        features: Audio-Features-Dictionary aus dem Summary-Block.

    Raises:
        sqlite3.Error: Bei Datenbankfehlern.
    """
    with sqlite3.connect(BEATBASE_DB_PATH) as conn:
        conn.execute(
            """UPDATE tracks
               SET danceability=?, acousticness=?, energy=?, instrumentalness=?,
                   liveness=?, speechiness=?, valence=?, loudness=?
               WHERE track_id=?""",
            (
                features.get("danceability", 0),
                features.get("acousticness", 0),
                features.get("energy", 0),
                features.get("instrumentalness", 0),
                features.get("liveness", 0),
                features.get("speechiness", 0),
                features.get("happiness", 0),
                features.get("loudness", 0),
                track_id,
            ),
        )
