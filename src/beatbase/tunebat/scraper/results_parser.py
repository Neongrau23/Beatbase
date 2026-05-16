"""Parser fuer Tunebat-Suchergebnisse (HTML -> strukturierte Dicts)."""

from urllib.parse import urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup


def parse_search_results(html_content: str) -> list[dict]:
    """Parst den HTML-Inhalt des Suchergebnis-Containers in eine Liste von Track-Dicts."""
    soup = BeautifulSoup(html_content, "html.parser")
    tracks = []

    rows = soup.find_all("div", class_="pDoqI")
    for row in rows:
        track = _parse_row(row, soup)
        if track:
            tracks.append(track)

    return tracks


def _parse_row(row, soup: BeautifulSoup) -> dict | None:
    """Extrahiert alle Felder aus einer einzelnen Ergebnis-Row."""
    info_link = row.find("a", href=lambda h: h and h.startswith("/Info/"))
    if not info_link:
        return None

    track: dict = {}
    track["tunebatUrl"] = "https://tunebat.com" + info_link.get("href")

    track_id = track["tunebatUrl"].rsplit("/", 1)[-1] if track["tunebatUrl"] else None

    img = info_link.find("img")
    track["imageUrl"] = img.get("src") if img else None

    artist_el = info_link.find("div", class_="_2zAVA")
    title_el = info_link.find("div", class_="aZDDf")

    if artist_el:
        track["artists"] = [a.strip() for a in artist_el.get_text(strip=True).split(",")]
    if title_el:
        track["title"] = title_el.get_text(strip=True)

    # Key, BPM, Camelot, Popularity aus den k43JJ-Blöcken
    stat_blocks = info_link.find_all("div", class_="k43JJ")
    for block in stat_blocks:
        value_el = block.find("p", class_="lAjUd")
        label_el = block.find("p", class_="hj07Z")
        if not value_el or not label_el:
            continue
        label = label_el.get_text(strip=True)
        value = value_el.get_text(strip=True)
        if label == "Key":
            track["key"] = value
        elif label == "BPM":
            track["bpm"] = int(value) if value.isdigit() else value
        elif label == "Camelot":
            track["camelot"] = value
        elif label == "Popularity":
            track["popularity"] = int(value) if value.isdigit() else value

    # Spotify & Songstats Links (liegen im Geschwister-div der Row)
    if track_id:
        spotify_link = row.find("a", attrs={"aria-label": "Spotify"})
        if not spotify_link:
            spotify_link = soup.find("a", href=lambda h: h and f"spotify.com/track/{track_id}" in h)
        track["spotifyUrl"] = spotify_link.get("href") if spotify_link else None

        songstats_link = row.find("a", attrs={"aria-label": "Songstats"})
        if not songstats_link:
            songstats_link = soup.find("a", href=lambda h: h and f"songstats.com/t/{track_id}" in h)
        raw = songstats_link.get("href") if songstats_link else None
        if raw:
            parsed = urlparse(raw)
            track["songstatsUrl"] = urlunparse(parsed._replace(query=urlencode({"source": "overview"})))
        else:
            track["songstatsUrl"] = None

    return track
