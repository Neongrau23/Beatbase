from bs4 import BeautifulSoup


def _extract_overview(soup: BeautifulSoup) -> dict:
    """SECTION: OVERVIEW - Extrahiert allgemeine Informationen, musikalische Details und Genre-Hashtags."""
    results = {}

    # MARK: - Metadaten (Artists, ISRC, Release Date etc.)
    rows = soup.find_all("div", style=lambda x: x and "display: flex" in x)
    targets = [
        "Artists:",
        "Collaborators:",
        "Record Labels:",
        "Distributors:",
        "Release Date:",
        "ISRCs:",
    ]

    for row in rows:
        label_span = row.find("span", style=lambda x: x and "color: rgb(171, 171, 171)" in x)
        if label_span and any(t in label_span.text for t in targets):
            label = label_span.text.strip().replace(":", "")
            vals = [b.find("span").text.strip() for b in row.find_all("div", style=lambda x: x and "background: rgb(46, 46, 46)" in x) if b.find("span")]
            if not vals:
                vals = [s.text.strip() for s in row.find_all("span", style=lambda x: x and "color: rgb(240, 240, 240)" in x) if s.text.strip()]
            if vals:
                results[label] = ", ".join(vals)

    # MARK: - Genres (Hashtags am Ende der Overview)
    # Wir suchen nach den Containern, die die Hashtags enthalten
    genre_tags = []
    # Alle Spans mit der Farbe rgb(240, 240, 240), die mit '#' beginnen
    all_spans = soup.find_all("span", style=lambda x: x and "color: rgb(240, 240, 240)" in x)
    for span in all_spans:
        txt = span.get_text(strip=True)
        if txt.startswith("#"):
            genre_tags.append(txt)

    # Falls das nicht klappt, versuchen wir es über die Container-Struktur
    if not genre_tags:
        genre_containers = soup.find_all("div", style=lambda x: x and "background-color: rgb(46, 46, 46)" in x and "margin-right: 8px" in x)
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
    cards = soup.find_all(
        "div",
        style=lambda x: x and ("background: rgb(35, 35, 35)" in x or "background-color: rgb(35, 35, 35)" in x),
    )
    for card in cards:
        label_node = card.find("span", style=lambda x: x and "font-size: 16px" in x)
        value_node = card.find(
            "span",
            style=lambda x: x and ("font-size: 30px" in x or "color: rgb(231, 35, 75)" in x),
        )
        if label_node and value_node:
            label = label_node.text.strip()
            if label in music_info_targets:
                results[label] = value_node.text.strip()

    return results
