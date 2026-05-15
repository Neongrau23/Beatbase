import sqlite3

from beatbase.core.config import BEATBASE_DB_PATH


# DEF: update_audio_features(track_id, features) -> None
def update_audio_features(track_id: str, features: dict) -> None:
    """Schreibt Audio-Features für einen Track in die lokale Beatbase-Datenbank.

    Args:
        track_id: Die interne Track-ID (Primärschlüssel in der `tracks`-Tabelle).
        features: Dictionary mit Audio-Feature-Werten. Fehlende Keys werden als 0 gewertet.

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
                features.get("Danceability", 0),
                features.get("Acousticness", 0),
                features.get("Energy", 0),
                features.get("Instrumentalness", 0),
                features.get("Liveness", 0),
                features.get("Speechiness", 0),
                features.get("Valence", 0),
                features.get("Loudness", 0),
                track_id,
            ),
        )
