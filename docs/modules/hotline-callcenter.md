# Hotline & Callcenter

Quellen:
- `src/beatbase/core/hotline.py`
- `src/beatbase/utils/callcenter.py`

Zweistufiger Datenfluss: **Hotline** ist die nackte Ablage, **Callcenter** die
Aggregations-Schicht.

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
bus.set("songstats", "Energy", 0.73)
bus.set("songstats", "Title", "Blinding Lights")
bus.set("genius", "url", "https://genius.com/...")
```

### Eigenschaften

- **Keine Logik, kein Schema.** Die Hotline kennt keine Typen, keine
  Pflichtfelder, keine Validierung.
- **Globaler Singleton.** Alle Module greifen auf dieselbe Instanz `bus` zu.
  Im Watcher-Loop ist das beabsichtigt; in Tests muss man entsprechend
  isolieren (`bus.clear()`).
- **Default-Fallback.** `bus.get(source, key)` gibt bei fehlenden Werten den
  scherzhaften Default `"kein anschluss unter dieser variable..."` zurück —
  unmissverständlich beim Debuggen.
- **Clear zwischen Songs.** Der Watcher ruft `bus.clear()` zu Beginn jedes
  `_handle_new_track`. Ohne das würden alte Werte ins nächste Summary lecken.

## Callcenter

```python
def build_song_summary() -> dict:
    raw = bus.get_all()
    summary = {
        "title": bus.get("songstats", "Title", default=None)
                 or bus.get("spotify", "name"),
        "isrc":  bus.get("spotify", "isrc", default=None)
                 or bus.get("songstats", "ISRCs"),
        "release_date": _determine_release_date(raw),
        "genius_url": bus.get("genius", "url"),
    }
    return summary
```

### Priorisierungsstrategie

Hier sitzt die quellenübergreifende Logik:

| Feld | Strategie |
|------|-----------|
| `title` | Songstats hat oft den exakteren Titel (inkl. Versionierung "- Remix"). Fallback auf Spotify-`name`. |
| `isrc` | Spotify als Primärquelle (offiziell vom Label). Songstats als Fallback. |
| `release_date` | **Ältestes** Datum aus allen Quellen — Spotify zeigt oft Re-Release-Daten, Songstats das Original. |
| `genius_url` | Nur Genius liefert das. |

`_determine_release_date` iteriert über alle `raw`-Quellen, sammelt alle
Felder mit Datum (`release_date`, `Release Date`, `Release date`) und gibt
den lexikografisch kleinsten String zurück — funktioniert für ISO-Daten
sauber.

### Erweitern

Neuer Extraktor `lastfm` mit Listener-Count? Einfach:

```python
bus.set("lastfm", "listeners", 12_345_678)
```

Im Callcenter ergänzen:

```python
summary["popularity"] = (
    bus.get("songstats", "Spotify Popularity", default=None)
    or bus.get("lastfm", "listeners")
)
```

Der Bus muss nicht geändert werden — er ist schema-frei.

## Warum dieses Muster?

**Alternative 1: Jeder Extraktor liefert ein typisiertes Song-Objekt.**
Problem: Bei N Quellen mit M Feldern entstehen schnell N×M Edge-Cases im
Merging. Außerdem muss jeder neue Extraktor das Zielschema kennen.

**Alternative 2: Zentrale Pipeline mit fixem Schritt-Schema.**
Problem: Inflexibel. Manche Quellen liefern Felder, die andere gar nicht
haben.

**Hotline/Callcenter:** Schreiber sind dumm, der eine Leser ist klug. Neue
Felder fließen ohne Schreiber-Änderungen ein; das Schema lebt nur an einer
Stelle.
