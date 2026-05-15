"""Extraktion von Lyrics, Credits und Tracklists aus geparstem Genius-HTML."""

import re

from bs4 import BeautifulSoup

from beatbase.core.config import GENIUS_URL


# DEF: Extrahiert Song-Details
def extrahiere_song_details_json(soup: BeautifulSoup) -> dict:
    """SECTION: EXTRACTION - Extrahiert Lyrics, Credits und Album-Tracklists aus Genius-HTML."""
    data = {
        "track_info": {},
        "credits": {},
        "lyrics": [],
        "album_tracklist": [],
        "about": {"bio": "", "q_and_a": []},
    }

    # MARK: - Track Info (Titel, Artist, Views, Release)
    title_elem = soup.find("h1")
    if title_elem:
        data["track_info"]["title"] = title_elem.get_text(strip=True)

    # Suche nach Header-Details für Artist und Stats
    # Oft in SongHeader-desktop__SongDetails oder ähnlichen Klassen
    header_details = soup.find("div", class_=re.compile(r"SongHeader-desktop__SongDetails", re.I))
    if header_details:
        artist_link = header_details.find("a", href=re.compile(r"/artists/"))
        if artist_link:
            data["track_info"]["artist"] = artist_link.get_text(strip=True)

    # Stats (Views etc)
    stats_container = soup.find("div", class_=re.compile(r"MetadataStats__Container", re.I))
    if stats_container:
        data["track_info"]["views"] = stats_container.get_text(strip=True)

    # MARK: - Lyrics Extraktion
    lyrics_containers = soup.find_all("div", {"data-lyrics-container": "true"})
    if lyrics_containers:
        full_lyrics_text = ""
        for container in lyrics_containers:
            # Annotation-Links entfernen
            for exclude in container.find_all("div", {"data-exclude-from-selection": "true"}):
                exclude.decompose()

            for br in container.find_all("br"):
                br.replace_with("\n")
            full_lyrics_text += container.get_text() + "\n"

        lines = [
            line_text.strip()
            for line_text in full_lyrics_text.split("\n")
            if line_text.strip()
        ]

        current_section = "[Lyrics]"
        current_lines = []

        for line in lines:
            if line.startswith("[") and line.endswith("]") and len(line) > 3:
                if current_lines:
                    data["lyrics"].append({"section": current_section, "lines": current_lines})
                    current_lines = []
                current_section = line
            else:
                current_lines.append(line)

        if current_lines:
            data["lyrics"].append({"section": current_section, "lines": current_lines})

    # MARK: - Credits Extraktion (Neu)
    # Nutzt die SongCredits__Columns Struktur
    credits_container = soup.find("div", class_=re.compile(r"SongCredits__Columns", re.I))
    if not credits_container:
        # Fallback auf generische Suche nach Credit-Containern
        credits_container = soup

    credit_items = credits_container.find_all("div", class_=re.compile(r"Credit__Container", re.I))
    for item in credit_items:
        label_elem = item.find("div", class_=re.compile(r"Credit__Label", re.I))
        contributor_elem = item.find("div", class_=re.compile(r"Credit__Contributor", re.I))

        if label_elem and contributor_elem:
            key = (
                label_elem.get_text(strip=True)
                .lower()
                .replace(" ", "_")
                .replace("©", "copyright")
                .replace("℗", "phonographic_copyright")
            )
            # Extrahiere alle Namen/Links aus dem Contributor-Feld
            names = []
            links = contributor_elem.find_all("a")
            if links:
                names = [a.get_text(strip=True) for a in links]
            else:
                # Falls keine Links da sind (z.B. bei Release Date), nimm den Text
                names = [contributor_elem.get_text(strip=True)]

            data["credits"][key] = names

    # MARK: - Album Tracklist (Neu)
    # Nutzt die AlbumTracklist__Container Struktur
    tracklist_container = soup.find("ol", class_=re.compile(r"AlbumTracklist__Container", re.I))
    if tracklist_container:
        tracks = tracklist_container.find_all(
            "li", class_=re.compile(r"AlbumTracklist__Track", re.I)
        )
        for track in tracks:
            track_info = {}
            # Nummer extrahieren
            num_elem = track.find("div", class_=re.compile(r"AlbumTracklist__TrackNumber", re.I))
            if num_elem:
                track_info["number"] = num_elem.get_text(strip=True).replace(".", "")

            # Name und Link extrahieren
            name_container = track.find(
                "div", class_=re.compile(r"AlbumTracklist__TrackName", re.I)
            )
            if name_container:
                # Link suchen
                link_elem = name_container.find("a")
                if link_elem:
                    track_info["title"] = link_elem.get_text(strip=True)
                    track_info["link"] = link_elem.get("href")
                    if track_info["link"] and not track_info["link"].startswith("http"):
                        track_info["link"] = GENIUS_URL + track_info["link"]
                else:
                    # Falls kein Link (z.B. der aktuelle Song in der Liste)
                    # Den Text holen, aber die Nummer vorne abschneiden
                    full_text = name_container.get_text(separator=" ", strip=True)
                    if num_elem:
                        full_text = full_text.replace(num_elem.get_text(strip=True), "").strip()
                    track_info["title"] = full_text

            if track_info:
                data["album_tracklist"].append(track_info)

    if not data.get("lyrics") and not data.get("credits"):
        # Minimal-Rückgabe bei Fehlschlag
        data["lyrics"] = [{"section": "[Info]", "lines": ["Keine Details Verfügbar"]}]

    return data
