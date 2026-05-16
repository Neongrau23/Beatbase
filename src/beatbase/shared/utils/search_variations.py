import re
from unicodedata import normalize


def _to_tunebat_slug(*parts: str) -> str:
    """Baut aus Teilen einen Tunebat-Suchslug: Leerzeichen und Sonderzeichen → Bindestriche."""
    combined = " ".join(p for p in parts if p and p.strip())
    norm = normalize("NFKD", combined).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-z0-9\s-]", " ", norm.lower())
    return re.sub(r"[\s-]+", "-", norm.strip())


# SECTION: HELPERS
def _join(*parts: str) -> str:
    """Verbindet Teile mit Leerzeichen, ignoriert leere Strings."""
    return " ".join(p for p in parts if p and p.strip())


# SECTION: SEARCH HANDLERS - Generiert Variationen für alle Extraktoren
def generate_variations(target_song: str, target_artists: list[str], limit: int = 30) -> list[str]:
    """ENTRY: Erstellt eine breite Palette an Suchbegriffen.
    Wiederverwendbar für Songstats, Genius, Spotify etc.
    """
    # 1. Normalisierung & Bereinigung
    # WHY: Unicode-Normalisierung (naïve -> naive) und Typografie-Fixes.
    s_norm = target_song.replace("’", "'").replace("‘", "'")
    s_norm = normalize("NFKD", s_norm).encode("ascii", "ignore").decode("ascii")

    clean_target = re.sub(r"(?i)\s*[\(\[]?\b(von|feat\.?|ft\.?|with)\b.*", "", s_norm).strip()
    clean_target = clean_target.rstrip("([ ")

    # Fix: Nur bei " - " splitten, nicht bei einfachem "-" (Lo-Fi)
    core_title = re.sub(r"\(.*?\)", "", clean_target).split(" - ")[0].strip()

    remix_tag = ""
    if "edit" in s_norm.lower():
        remix_tag = "Edit"
    elif "remix" in s_norm.lower():
        remix_tag = "Remix"

    # Alle Klammern sammeln, Feature-Blocks ignorieren
    parens = re.findall(r"\((.*?)\)", s_norm)
    feat_pattern = r"(?i)\b(feat\.?|ft\.?|with|von)\b"
    meaningful_parens = [re.sub(feat_pattern + r".*", "", p).strip() for p in parens if not re.search(feat_pattern, p)]
    parens_text = meaningful_parens[0] if meaningful_parens else ""

    artists_str = " ".join(target_artists)
    main_artist = target_artists[0] if target_artists else ""

    # 2. Bausteine
    t_full = clean_target.replace("-", " ")

    raw_vars = [
        target_song,  # Original
        _join(t_full, artists_str),
        _join(core_title, remix_tag, artists_str),
        _join(core_title, artists_str),
        _join(core_title, parens_text, artists_str),
        _join(t_full, main_artist),
        _join(artists_str, t_full),
        _join(artists_str, core_title),
        _join(main_artist, core_title),
        _join(" & ".join(target_artists[:2]), core_title),
        f"{artists_str} - {core_title}",
        f"{main_artist} - {core_title}",  # NEU: Dash-Variante
        f"{parens_text} {main_artist}",  # NEU: Mix + Artist
        _join(core_title, main_artist),
        f"{core_title} | {main_artist}",
        t_full,
        core_title,
    ]

    # 3. Deduplizierung & Säuberung
    unique_queries = []
    seen_queries = set()

    for q in raw_vars:
        q = q.strip()
        if q and q.lower() not in seen_queries:
            unique_queries.append(q)
            seen_queries.add(q.lower())

    return unique_queries[:limit]


# DEF: generate_tunebat_variations(song, artists, album) -> list[str]
def generate_tunebat_variations(
    song: str, artists: list[str], album: str | None = None
) -> list[str]:
    """Erstellt Tunebat-spezifische Suchbegriffe im Slug-Format (Leerzeichen → Bindestriche).

    Reihenfolge: Album/Single zuerst, dann Songtitel — jeweils mit allen
    Kuenstlern und danach nur mit dem Hauptkuenstler.
    """
    s_norm = song.replace("’", "'").replace("‘", "'")
    s_norm = normalize("NFKD", s_norm).encode("ascii", "ignore").decode("ascii")
    clean_song = re.sub(
        r"(?i)\s*[\(\[]?\b(von|feat\.?|ft\.?|with)\b.*", "", s_norm
    ).strip().rstrip("([ ")
    core_title = re.sub(r"\(.*?\)", "", clean_song).split(" - ")[0].strip()

    artists_str = " ".join(artists)
    main_artist = artists[0] if artists else ""
    multi = len(artists) > 1

    raw: list[str] = []

    if album:
        raw.append(_to_tunebat_slug(album, artists_str))
        if multi:
            raw.append(_to_tunebat_slug(album, main_artist))

    raw.append(_to_tunebat_slug(clean_song, artists_str))
    if multi:
        raw.append(_to_tunebat_slug(clean_song, main_artist))

    if core_title != clean_song:
        raw.append(_to_tunebat_slug(core_title, artists_str))
        if multi:
            raw.append(_to_tunebat_slug(core_title, main_artist))

    seen: set[str] = set()
    result: list[str] = []
    for q in raw:
        if q and q not in seen:
            result.append(q)
            seen.add(q)
    return result


# DEF: extract_featured_artists(song_title) -> list[str]
def extract_featured_artists(song_title: str) -> list[str]:
    """Extrahiert Künstler, die im Songtitel versteckt sind (feat., ft., with, von).

    Gibt eine Liste der gefundenen Künstlernamen zurück (kann leer sein).
    Mutiert NICHT die Eingabe.
    """
    match = re.search(r"(?i)\b(von|feat\.?|ft\.?|with)\b(.*)", song_title)
    if not match:
        return []

    raw = match.group(2).strip()
    # Bereinigung: Falls "feat. Artist" gematcht wurde, kann am Anfang noch ein Punkt sein
    raw = re.sub(r"^[.\s]+", "", raw)
    # Entferne schließende Klammern am Ende des gesamten Blocks
    raw = raw.rstrip(")]")

    result = []
    # Splitten nach gängigen Trennern: , & | and x vs. vs
    for name in re.split(r"[,&|]| and | x | vs\.? ", raw):
        name = name.strip().rstrip(")]")
        if name:
            result.append(name)
    return result
