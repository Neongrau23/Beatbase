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
    audio_features = bus.get("tunebat", "audio_features", default=None)

    # 4. Lyrics (Exklusiv von Genius)
    genius_data = bus.get("genius", "data", default={})
    lyrics = genius_data.get("lyrics")

    # 5. SongBPM (Analyse & Links)
    songbpm_data = bus.get("songbpm", "data", default={})

    # Zusammenführung in das Master-Objekt
    master = {
        "meta": {k: v for k, v in meta.items() if v is not None},
        "music_theory": {k: v for k, v in music_theory.items() if v is not None},
        "audio_features": audio_features,
        "analysis": songbpm_data.get("description"),
        "lyrics": lyrics,
        "links": {
            "genius": genius_data.get("url") or bus.get("genius", "url", default=None),
            "spotify": bus.get("spotify", "url", default=None),
            "tunebat": bus.get("tunebat", "url", default=None),
            "songstats": bus.get("songstats", "url", default=None),
            "songbpm": songbpm_data.get("url"),
        },
    }

    # Säubern: Entferne leere Top-Level Objekte (außer meta)
    final_master = {k: v for k, v in master.items() if v is not None and (not isinstance(v, dict) or v)}
    return final_master


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
