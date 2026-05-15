# SECTION: CALLCENTER - Hier werden die nackten Hotline-Daten strukturiert
import json

from beatbase.core.hotline import bus


def build_song_summary() -> dict:
    """
    DEF: Nimmt die nackten Daten der Hotline entgegen und baut die Master-Struktur.
    Das Callcenter ist das Gehirn, das alle Quellen (Spotify, Genius, Tunebat, Songstats)
    zu einem konsistenten Datensatz zusammenführt.
    """
    raw = bus.get_all()

    # 1. Metadaten-Block (meta)
    # Priorisierung der Felder für maximale Datenabdeckung
    meta = {
        "title": bus.get("spotify", "name", default=None) or bus.get("songstats", "Title", default=None) or bus.get("tunebat", "title", default=None),
        "artist": ", ".join(bus.get("spotify", "artists", default=[]))
        or bus.get("songstats", "Artists", default=None)
        or bus.get("songstats", "Artist", default=None)
        or bus.get("tunebat", "artist", default=None),
        "album": bus.get("tunebat", "album", default=None) or bus.get("spotify", "album", default=None),
        "release_date": bus.get("tunebat", "release_date", default=None)
        or bus.get("spotify", "release_date", default=None)
        or bus.get("songstats", "Release Date", default=None)
        or _determine_release_date(raw),
        "isrc": bus.get("spotify", "isrc", default=None) or bus.get("songstats", "ISRCs", default=None) or bus.get("songstats", "isrc", default=None),
        "explicit": bus.get("tunebat", "explicit", default=None) or bus.get("spotify", "explicit", default=None),
        "label": bus.get("tunebat", "label", default=None) or bus.get("songstats", "Record Labels", default=None),
        "genres": bus.get("songstats", "Genres", default=None),
    }

    # 2. Musik-Theorie & Metriken (music_theory)
    music_theory = {
        "bpm": bus.get("tunebat", "bpm", default=None) or bus.get("songstats", "BPM", default=None),
        "key": bus.get("tunebat", "key", default=None) or bus.get("songstats", "Key", default=None),
        "camelot": bus.get("tunebat", "camelot", default=None),
        "duration": bus.get("tunebat", "duration", default=None),
        "popularity": bus.get("tunebat", "popularity", default=None),
    }

    # 3. Audio Features (aus Tunebat)
    raw_audio = bus.get("tunebat", "audio_features", default={})
    audio_features = {
        "acousticness": raw_audio.get("acousticness", None),
        "danceability": raw_audio.get("danceability", None),
        "energy": raw_audio.get("energy", None),
        "instrumentalness": raw_audio.get("instrumentalness", None),
        "liveness": raw_audio.get("liveness", None),
        "speechiness": raw_audio.get("speechiness", None),
        "happiness": raw_audio.get("happiness", None),
        "loudness": raw_audio.get("loudness", None),
    }

    # 4. Genius Daten (Lyrics, Tracklist & Credits)
    genius_data = bus.get("genius", "data", default={})
    lyrics = genius_data.get("lyrics", [])
    album_tracklist = genius_data.get("album_tracklist", [])
    credits = genius_data.get("credits", {})

    # 5. SongBPM (Analyse & Links)
    songbpm_data = bus.get("songbpm", "data", default={})

    # Zusammenführung in das Master-Objekt (festes Schema)
    master = {
        "meta": meta,
        "music_theory": music_theory,
        "audio_features": audio_features,
        "analysis": songbpm_data.get("description", None),
        "lyrics": lyrics,
        "album_tracklist": album_tracklist,
        "credits": credits,
        "links": {
            "genius": genius_data.get("url") or bus.get("genius", "url", default=None),
            "spotify": bus.get("spotify", "url", default=None),
            "tunebat": bus.get("tunebat", "url", default=None),
            "songstats": bus.get("songstats", "url", default=None),
            "songbpm": songbpm_data.get("url", None),
        },
    }

    return master


def get_summary_json() -> str:
    """Gibt die Zusammenfassung als formatierte JSON-Zeichenkette zurück."""
    return json.dumps(build_song_summary(), indent=4, ensure_ascii=False)


def _determine_release_date(raw: dict) -> str:
    """HELP: Sucht das älteste Datum aus allen Quellen."""
    dates = []
    for source_data in raw.values():
        if not isinstance(source_data, dict):
            continue
        for key in ["release_date", "Release Date", "Release date"]:
            val = source_data.get(key)
            if val:
                dates.append(str(val))

    return sorted(dates)[0] if dates else None
