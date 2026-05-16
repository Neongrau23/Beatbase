"""SQLite-Speicher fuer Song-Summaries (flache Tabelle, Track-ID als PK)."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/songs.db")


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            track_id TEXT PRIMARY KEY,
            title TEXT,
            artist TEXT,
            album TEXT,
            release_date TEXT,
            isrc TEXT,
            explicit TEXT,
            label TEXT,
            genres TEXT,
            bpm TEXT,
            key TEXT,
            camelot TEXT,
            duration TEXT,
            popularity TEXT,
            acousticness TEXT,
            danceability TEXT,
            energy TEXT,
            instrumentalness TEXT,
            liveness TEXT,
            speechiness TEXT,
            happiness TEXT,
            loudness TEXT,
            analysis TEXT,
            lyrics TEXT,
            album_tracklist TEXT,
            credits TEXT,
            link_genius TEXT,
            link_spotify TEXT,
            link_tunebat TEXT,
            link_songstats TEXT,
            link_songbpm TEXT,
            saved_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_song_summary(track_id: str, summary: dict) -> None:
    """Speichert eine Song-Summary in die DB. Ueberschreibt bei gleichem track_id."""
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()

    meta = summary.get("meta", {})
    theory = summary.get("music_theory", {})
    audio = summary.get("audio_features", {})
    links = summary.get("links", {})

    conn.execute(
        """INSERT OR REPLACE INTO songs
           (track_id, title, artist, album, release_date, isrc, explicit,
            label, genres, bpm, key, camelot, duration, popularity,
            acousticness, danceability, energy, instrumentalness,
            liveness, speechiness, happiness, loudness,
            analysis, lyrics, album_tracklist, credits,
            link_genius, link_spotify, link_tunebat, link_songstats,
            link_songbpm, saved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            track_id,
            meta.get("title"),
            meta.get("artist"),
            meta.get("album"),
            meta.get("release_date"),
            meta.get("isrc"),
            meta.get("explicit"),
            meta.get("label"),
            meta.get("genres"),
            theory.get("bpm"),
            theory.get("key"),
            theory.get("camelot"),
            theory.get("duration"),
            theory.get("popularity"),
            audio.get("acousticness"),
            audio.get("danceability"),
            audio.get("energy"),
            audio.get("instrumentalness"),
            audio.get("liveness"),
            audio.get("speechiness"),
            audio.get("happiness"),
            audio.get("loudness"),
            summary.get("analysis"),
            json.dumps(summary.get("lyrics", []), ensure_ascii=False),
            json.dumps(summary.get("album_tracklist", []), ensure_ascii=False),
            json.dumps(summary.get("credits", {}), ensure_ascii=False),
            links.get("genius"),
            links.get("spotify"),
            links.get("tunebat"),
            links.get("songstats"),
            links.get("songbpm"),
            now,
        ),
    )
    conn.commit()
    conn.close()
