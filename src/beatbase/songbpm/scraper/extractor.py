"""Extraktion von Metadaten und Beschreibungen aus SongBPM-HTML."""

import json
import re

import requests
from bs4 import BeautifulSoup

from beatbase.utils.log import log_status


# DEF: extract_song_info(url) -> dict | None
def extract_song_info(url: str) -> dict | None:
    """SECTION: EXTRACTION - Extrahiert Metadaten und die Beschreibung von einer SongBPM Detailseite."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        # MARK: - Metriken Parsing
        def metric(name):
            dt = soup.find("dt", string=re.compile(name))
            if not dt:
                return None
            return dt.find_next_sibling("dd").get_text(strip=True)

        # MARK: - Entity Extraktion
        artist = soup.find("h2").get_text(strip=True) if soup.find("h2") else None
        song_title = soup.find("h1").get_text(strip=True) if soup.find("h1") else None

        # Die wichtige Vibe-Beschreibung
        desc_div = soup.find("div", class_=re.compile(r"lg:prose-xl"))
        description = desc_div.get_text(" ", strip=True) if desc_div else None

        spotify_link = soup.find("a", href=re.compile(r"spotify\.com/track"))

        details = {
            "artist": artist,
            "title": song_title,
            "key": metric("Key"),
            "duration": metric("Duration"),
            "bpm": metric(r"Tempo \(BPM\)"),
            "description": description,
            "spotify_url": spotify_link["href"] if spotify_link else None,
            "url": url,
        }

        # Nur gefüllte Werte behalten
        details = {k: v for k, v in details.items() if v is not None}

        log_status(f"✅ SongBPM Details geladen: {details.get('description', 'Keine Beschreibung')[:100]}...")
        log_status(f"📊 SongBPM Daten: {json.dumps(details, indent=4, ensure_ascii=False)}")
        return details

    except Exception as e:
        log_status(f"❌ Fehler beim Laden von SongBPM Details: {e}")
        return None
