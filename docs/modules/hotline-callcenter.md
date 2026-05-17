# Hotline & Callcenter

Quellen:
- `src/beatbase/core/hotline.py`
- `src/beatbase/shared/utils/callcenter.py`

Zweistufiger Datenfluss: **Hotline** ist die nackte Ablage, **Callcenter** die
Aggregations-Schicht mit deklarativem Schema.

## Hotline

```python
@dataclass
class Hotline:
    storage: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set(self, source: str, key: str, value: Any): ...
    def get(self, source, key, default="kein anschluss unter dieser variable..."): ...
    def get_all(self) -> dict: ...
    def clear(self) -> None: ...

bus = Hotline()  # globale Instanz
```

### Verwendung

Extraktoren schreiben ihre Rohdaten unter ihrem Quellennamen:

```python
bus.set("spotify", "id", "abc123")
bus.set("spotify", "isrc", "USUG11904206")
bus.set("tunebat", "bpm", "171")
bus.set("tunebat", "audio_features", {"energy": "85", "danceability": "72"})
bus.set("songstats", "Title", "Blinding Lights")
bus.set("songstats", "Genres", "Synth-pop, Pop")
bus.set("genius", "data", {"lyrics": [...], "credits": {...}})
bus.set("songbpm", "data", {"description": "energetic", "url": "..."})
```

### Eigenschaften

- **Keine Logik, kein Schema.** Die Hotline kennt keine Typen, keine
  Pflichtfelder, keine Validierung.
- **Globaler Singleton.** Alle Module greifen auf dieselbe Instanz `bus` zu.
  Im Watcher-Loop ist das beabsichtigt; in Tests muss man entsprechend
  isolieren (`bus.clear()`).
- **Default-Fallback.** `bus.get(source, key)` gibt bei fehlenden Werten den
  scherzhaften Default `"kein anschluss unter dieser variable..."` zurück —
  unmissverständlich beim Debuggen. Wer einen sauberen `None` will, übergibt
  `default=None`.
- **Clear zwischen Songs.** Der Watcher ruft `bus.clear()` zu Beginn jedes
  `_handle_new_track`. Ohne das würden alte Werte ins nächste Summary lecken.

## Callcenter

Die Logik-Schicht. Ein **deklaratives Schema** beschreibt pro Feld, welche
Quellen mit welcher Priorität abgefragt werden.

### Bausteine

```python
@dataclass(frozen=True)
class Source:
    name: str                                # Hotline-Source-Key
    key: str                                 # Schlüssel innerhalb der Quelle
    transform: Callable[[Any], Any] | None = None  # Optionale Wert-Transformation

@dataclass(frozen=True)
class FieldSpec:
    sources: tuple[Source, ...]              # Geordnete Quell-Liste
    fallback: Callable[[], Any] | None = None  # Wenn alle Quellen leer
```

### Auswertung

```python
def _pick(spec: FieldSpec) -> Any:
    for source in spec.sources:
        value = bus.get(source.name, source.key, default=None)
        if source.transform is not None:
            value = source.transform(value)
        if value:
            return value
    return spec.fallback() if spec.fallback else None
```

Die erste truthy Quelle gewinnt; der Fallback greift nur, wenn alle Quellen
leer sind.

### Schema-Definitionen

Drei Blöcke werden über das Schema gebildet, plus drei direkte Lookups:

```python
META = {
    "title": FieldSpec(sources=(
        Source("spotify", "name"),
        Source("songstats", "Title"),
        Source("tunebat", "title"),
    )),
    "artist": FieldSpec(sources=(
        Source("spotify", "artists", transform=_join_list),  # Liste → String
        Source("songstats", "Artists"),
        Source("songstats", "Artist"),
        Source("tunebat", "artist"),
    )),
    "release_date": FieldSpec(
        sources=(
            Source("tunebat", "release_date"),
            Source("spotify", "release_date"),
            Source("songstats", "Release Date"),
        ),
        fallback=_determine_release_date,  # ältestes Datum aus allen Quellen
    ),
    ...
}

MUSIC_THEORY = {
    "bpm": FieldSpec(sources=(Source("tunebat", "bpm"), Source("songstats", "BPM"))),
    "key": FieldSpec(sources=(Source("tunebat", "key"), Source("songstats", "Key"))),
    ...
}

LINKS = {
    # Genius: Watcher legt sowohl flach als auch geschachtelt ab;
    # historisch wurde zuerst aus dem `data`-Block gelesen.
    "genius": FieldSpec(sources=(
        Source("genius", "data", transform=_from_dict("url")),
        Source("genius", "url"),
    )),
    "spotify":   FieldSpec(sources=(Source("spotify", "url"),)),
    "tunebat":   FieldSpec(sources=(Source("tunebat", "url"),)),
    "songstats": FieldSpec(sources=(Source("songstats", "url"),)),
    "songbpm":   FieldSpec(sources=(Source("songbpm", "data", transform=_from_dict("url")),)),
}
```

### Master-Struktur

`build_song_summary()` erzeugt das feste Master-Schema:

```python
{
    "meta": {"title": ..., "artist": ..., "album": ..., "release_date": ...,
             "isrc": ..., "explicit": ..., "label": ..., "genres": ...},
    "music_theory": {"bpm": ..., "key": ..., "camelot": ..., "duration": ...,
                     "popularity": ...},
    "audio_features": {"acousticness": ..., "danceability": ..., "energy": ...,
                       "instrumentalness": ..., "liveness": ..., "speechiness": ...,
                       "happiness": ..., "loudness": ...},
    "analysis":       <songbpm.description>,
    "lyrics":         <genius.data.lyrics>,
    "album_tracklist": <genius.data.album_tracklist>,
    "credits":        <genius.data.credits>,
    "links": {"genius": ..., "spotify": ..., "tunebat": ..., "songstats": ...,
              "songbpm": ...},
}
```

`audio_features` wird aus `bus.get("tunebat", "audio_features")` als
geschachteltes Dict gelesen (keine Multi-Source-Priorisierung — Tunebat ist
aktuell die einzige Quelle).

### Erweitern

Neue Datenquelle `lastfm` mit Listener-Count?

1. Extraktor schreibt: `bus.set("lastfm", "listeners", 12_345_678)`.
2. Im Callcenter den entsprechenden Block ergänzen, z. B. in `MUSIC_THEORY`:
   ```python
   "popularity": FieldSpec(sources=(
       Source("tunebat", "popularity"),
       Source("lastfm", "listeners"),
   )),
   ```

Der Bus muss nicht geändert werden — er ist schema-frei. Das Schema lebt
ausschließlich im Callcenter.

## Warum dieses Muster?

**Alternative 1: Jeder Extraktor liefert ein typisiertes Song-Objekt.**
Problem: Bei N Quellen mit M Feldern entstehen schnell N×M Edge-Cases im
Merging. Außerdem muss jeder neue Extraktor das Zielschema kennen.

**Alternative 2: Zentrale Pipeline mit fixem Schritt-Schema.**
Problem: Inflexibel. Manche Quellen liefern Felder, die andere gar nicht
haben.

**Hotline/Callcenter mit deklarativem Schema:** Schreiber sind dumm; der eine
Leser ist klug und macht seine Priorisierung explizit. Neue Felder fließen
ohne Schreiber-Änderungen ein; das Schema lebt nur an einer Stelle und ist
leicht zu lesen.
