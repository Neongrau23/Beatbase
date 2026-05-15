"""SECTION: CALLCENTER - Hier werden die nackten Hotline-Daten strukturiert.

Schema-getriebene Aggregation: Pro Feld wird eine geordnete Liste von Quellen
deklariert, aus der die erste nicht-leere Quelle gewinnt. Renamings oder
fehlende Keys werden so deutlich sichtbar, statt sich in einer `or`-Kette zu
verstecken.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from beatbase.core.hotline import bus


# SECTION: SCHEMA - Bausteine für die deklarative Feld-Priorisierung
@dataclass(frozen=True)
class Source:
    """Eine einzelne Datenquelle für ein Feld.

    Attributes:
        name: Hotline-Source-Key (z. B. ``"spotify"``).
        key: Schlüssel innerhalb der Quelle.
        transform: Optionale Wert-Transformation (z. B. Liste → String).
    """

    name: str
    key: str
    transform: Callable[[Any], Any] | None = None


@dataclass(frozen=True)
class FieldSpec:
    """Beschreibt, wie ein Feld aus dem Bus zusammengesetzt wird.

    Die Quellen werden in Reihenfolge geprüft; der erste truthy Wert gewinnt.
    `fallback` greift nur, wenn alle Quellen leer sind.
    """

    sources: tuple[Source, ...]
    fallback: Callable[[], Any] | None = None


# SECTION: TRANSFORMS
def _join_list(value: Any) -> str | None:
    """Liste → kommaseparierter String. None/leere Liste → None.

    Wird für Spotify-Artists-Listen benötigt, die zu einem String zusammengeführt
    werden müssen, während andere Quellen den String direkt liefern.
    """
    if isinstance(value, list) and value:
        return ", ".join(value)
    if isinstance(value, str):
        return value
    return None


def _from_dict(subkey: str) -> Callable[[Any], Any]:
    """Transform-Factory: liest ``subkey`` aus einem dict-Wert.

    Wird genutzt, um in geschachtelten Quellen (z. B. ``genius.data``,
    ``songbpm.data``) einen Unter-Schlüssel zu adressieren.
    """

    def transform(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get(subkey)
        return None

    return transform


# SECTION: PICKER
def _pick(spec: FieldSpec) -> Any:
    """Wertet eine FieldSpec gegen den globalen Bus aus.

    Geht die Quellen in Reihenfolge durch, optional mit Transform. Der erste
    truthy Wert wird zurückgegeben; bei vollständigem Fehlschlag wird der
    Fallback (falls vorhanden) aufgerufen, sonst None.
    """
    for source in spec.sources:
        value = bus.get(source.name, source.key, default=None)
        if source.transform is not None:
            value = source.transform(value)
        if value:
            return value
    return spec.fallback() if spec.fallback else None


# SECTION: FALLBACKS
def _determine_release_date() -> str | None:
    """HELP: Sucht das älteste Release-Datum aus allen Quellen im Bus."""
    dates: list[str] = []
    for source_data in bus.get_all().values():
        if not isinstance(source_data, dict):
            continue
        for key in ("release_date", "Release Date", "Release date"):
            val = source_data.get(key)
            if val:
                dates.append(str(val))
    return sorted(dates)[0] if dates else None


# SECTION: FIELD SCHEMAS - Die Priorisierungen pro Block
# WHY: Reihenfolge der Quellen reflektiert die historisch bewährte Priorität.
META: dict[str, FieldSpec] = {
    "title": FieldSpec(sources=(
        Source("spotify", "name"),
        Source("songstats", "Title"),
        Source("tunebat", "title"),
    )),
    "artist": FieldSpec(sources=(
        Source("spotify", "artists", transform=_join_list),
        Source("songstats", "Artists"),
        Source("songstats", "Artist"),
        Source("tunebat", "artist"),
    )),
    "album": FieldSpec(sources=(
        Source("tunebat", "album"),
        Source("spotify", "album"),
    )),
    "release_date": FieldSpec(
        sources=(
            Source("tunebat", "release_date"),
            Source("spotify", "release_date"),
            Source("songstats", "Release Date"),
        ),
        fallback=_determine_release_date,
    ),
    "isrc": FieldSpec(sources=(
        Source("spotify", "isrc"),
        Source("songstats", "ISRCs"),
        Source("songstats", "isrc"),
    )),
    "explicit": FieldSpec(sources=(
        Source("tunebat", "explicit"),
        Source("spotify", "explicit"),
    )),
    "label": FieldSpec(sources=(
        Source("tunebat", "label"),
        Source("songstats", "Record Labels"),
    )),
    "genres": FieldSpec(sources=(
        Source("songstats", "Genres"),
    )),
}

MUSIC_THEORY: dict[str, FieldSpec] = {
    "bpm": FieldSpec(sources=(Source("tunebat", "bpm"), Source("songstats", "BPM"))),
    "key": FieldSpec(sources=(Source("tunebat", "key"), Source("songstats", "Key"))),
    "camelot": FieldSpec(sources=(Source("tunebat", "camelot"),)),
    "duration": FieldSpec(sources=(Source("tunebat", "duration"),)),
    "popularity": FieldSpec(sources=(Source("tunebat", "popularity"),)),
}

LINKS: dict[str, FieldSpec] = {
    # WHY: Genius wird vom Watcher sowohl als ``data``-Block als auch flach abgelegt;
    # historisch wurde zuerst aus dem Block gelesen.
    "genius": FieldSpec(sources=(
        Source("genius", "data", transform=_from_dict("url")),
        Source("genius", "url"),
    )),
    "spotify": FieldSpec(sources=(Source("spotify", "url"),)),
    "tunebat": FieldSpec(sources=(Source("tunebat", "url"),)),
    "songstats": FieldSpec(sources=(Source("songstats", "url"),)),
    "songbpm": FieldSpec(sources=(
        Source("songbpm", "data", transform=_from_dict("url")),
    )),
}

# Audio Features liegen als geschachteltes dict unter ("tunebat", "audio_features").
AUDIO_FEATURE_KEYS: tuple[str, ...] = (
    "acousticness",
    "danceability",
    "energy",
    "instrumentalness",
    "liveness",
    "speechiness",
    "happiness",
    "loudness",
)


# SECTION: BUILDER - Public API
def build_song_summary() -> dict:
    """ENTRY: Baut die strukturierte Master-Ansicht aus den Hotline-Rohdaten.

    Das Callcenter ist das Gehirn, das alle Quellen (Spotify, Genius, Tunebat,
    Songstats, SongBPM) zu einem konsistenten Datensatz zusammenführt. Die
    Priorisierungslogik steht deklarativ in den Schema-Dicts oben.
    """
    raw_audio = bus.get("tunebat", "audio_features", default={}) or {}
    genius_data = bus.get("genius", "data", default={}) or {}
    songbpm_data = bus.get("songbpm", "data", default={}) or {}

    return {
        "meta": {field: _pick(spec) for field, spec in META.items()},
        "music_theory": {field: _pick(spec) for field, spec in MUSIC_THEORY.items()},
        "audio_features": {k: raw_audio.get(k) for k in AUDIO_FEATURE_KEYS},
        "analysis": songbpm_data.get("description"),
        "lyrics": genius_data.get("lyrics", []),
        "album_tracklist": genius_data.get("album_tracklist", []),
        "credits": genius_data.get("credits", {}),
        "links": {field: _pick(spec) for field, spec in LINKS.items()},
    }


def get_summary_json() -> str:
    """Gibt die Zusammenfassung als formatierte JSON-Zeichenkette zurück."""
    return json.dumps(build_song_summary(), indent=4, ensure_ascii=False)
