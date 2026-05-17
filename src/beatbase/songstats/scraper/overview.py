import re

from bs4 import BeautifulSoup


def _extract_overview(soup: BeautifulSoup) -> dict:
    """SECTION: OVERVIEW - Liest Metadaten, Genre-Hashtags und Music-Info aus der Seite."""
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

    label_color = re.compile(r"color:\s*rgb\(171,\s*171,\s*171\)")
    pill_bg = re.compile(r"background:\s*rgb\(46,\s*46,\s*46\)")
    light_text = re.compile(r"color:\s*rgb\(240,\s*240,\s*240\)")
    for row in rows:
        label_span = row.find("span", style=label_color)
        if label_span and any(t in label_span.text for t in targets):
            label = label_span.text.strip().replace(":", "")
            vals = [b.find("span").text.strip() for b in row.find_all("div", style=pill_bg) if b.find("span")]
            if not vals:
                vals = [s.text.strip() for s in row.find_all("span", style=light_text) if s.text.strip()]
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
            if not style_str:
                return False
            return "background-color: rgb(46, 46, 46)" in style_str and "margin-right: 8px" in style_str

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
    card_bg = re.compile(r"background(?:-color)?:\s*rgb\(35,\s*35,\s*35\)")
    label_style = re.compile(r"font-size:\s*16px")
    value_style = re.compile(r"font-size:\s*30px|color:\s*rgb\(231,\s*35,\s*75\)")
    cards = soup.find_all("div", style=card_bg)
    for card in cards:
        label_node = card.find("span", style=label_style)
        value_node = card.find("span", style=value_style)
        if label_node and value_node:
            label = label_node.text.strip()
            if label in music_info_targets:
                results[label] = value_node.text.strip()

    return results
