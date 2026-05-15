import re

from bs4 import BeautifulSoup


def _extract_overview(soup: BeautifulSoup) -> dict:
    """SECTION: OVERVIEW - Extrahiert allgemeine Informationen, musikalische Details und Genre-Hashtags."""
    results = {}

    # MARK: - Metadaten (Artists, ISRC, Release Date etc.)
    rows = soup.find_all("div", style=re.compile(r"display:\s*flex"))
    targets = [
        "Artists:",
        "Collaborators:",
        "Record Labels:",
        "Distributors:",
        "Release Date:",
        "ISRCs:",
    ]

    for row in rows:
        label_span = row.find("span", style=re.compile(r"color:\s*rgb\(171,\s*171,\s*171\)"))
        if label_span and any(t in label_span.text for t in targets):
            label = label_span.text.strip().replace(":", "")
            vals = [b.find("span").text.strip() for b in row.find_all("div", style=re.compile(r"background:\s*rgb\(46,\s*46,\s*46\)")) if b.find("span")]
            if not vals:
                vals = [s.text.strip() for s in row.find_all("span", style=re.compile(r"color:\s*rgb\(240,\s*240,\s*240\)")) if s.text.strip()]
            if vals:
                results[label] = ", ".join(vals)

    # MARK: - Genres (Hashtags am Ende der Overview)
    # Wir suchen nach den Containern, die die Hashtags enthalten
    genre_tags = []
    # Alle Spans mit der Farbe rgb(240, 240, 240), die mit '#' beginnen
    all_spans = soup.find_all("span", style=re.compile(r"color:\s*rgb\(240,\s*240,\s*240\)"))
    for span in all_spans:
        txt = span.get_text(strip=True)
        if txt.startswith("#"):
            genre_tags.append(txt)

    # Falls das nicht klappt, versuchen wir es über die Container-Struktur
    if not genre_tags:

        def is_genre_container(style_str: str | None) -> bool:
            return bool(style_str and "background-color: rgb(46, 46, 46)" in style_str and "margin-right: 8px" in style_str)

        genre_containers = soup.find_all("div", style=is_genre_container)
        for container in genre_containers:
            span = container.find("span")
            if span:
                txt = span.get_text(strip=True)
                if txt:
                    genre_tags.append(txt)

    if genre_tags:
        # Duplikate entfernen und sortieren
        results["Genres"] = ", ".join(sorted(list(set(genre_tags))))

    # MARK: - Music Info (Tempo, Key, Duration)
    music_info_targets = {"Duration", "Key", "Tempo", "Time Signature"}
    cards = soup.find_all("div", style=re.compile(r"background(?:-color)?:\s*rgb\(35,\s*35,\s*35\)"))
    for card in cards:
        label_node = card.find("span", style=re.compile(r"font-size:\s*16px"))
        value_node = card.find("span", style=re.compile(r"font-size:\s*30px|color:\s*rgb\(231,\s*35,\s*75\)"))
        if label_node and value_node:
            label = label_node.text.strip()
            if label in music_info_targets:
                results[label] = value_node.text.strip()

    return results
