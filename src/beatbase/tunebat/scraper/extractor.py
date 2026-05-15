"""Datenextraktion für eine geladene Tunebat-Song-Seite.

Die Seite ist in vier Bereiche aufgeteilt, die unterschiedliche CSS-Klassen
benutzen. Jede Sektion bekommt einen eigenen Helper, damit ein Layout-Wechsel
nur einen Block bricht.
"""

from playwright.sync_api import Page

from beatbase.utils.log import log_status

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


# DEF: Liest Key, BPM, Duration etc.
def _extract_metrics(page: Page) -> dict:
    """SECTION: METRICS - Liest die Werte aus den .yIPfN-Containern (Key/BPM/Duration)."""
    results: dict = {}
    try:
        containers = page.locator(".yIPfN")
        for i in range(containers.count()):
            container = containers.nth(i)
            value = container.locator("h3").inner_text().strip()
            label = (
                container.locator("span.ant-typography-secondary")
                .inner_text()
                .strip()
                .lower()
            )
            results[label] = value
    except Exception:
        pass
    return results


# DEF: Liest Progress-basierte Metriken (Popularity, Energy, ...)
def _extract_progress_metrics(page: Page) -> dict:
    """SECTION: PROGRESS - Liest die Werte aus den ._1MCwQ-Progress-Containern."""
    results: dict = {}
    try:
        containers = page.locator("._1MCwQ")
        for i in range(containers.count()):
            container = containers.nth(i)
            value_elem = container.locator(".ant-progress-text")
            label_elem = container.locator("span.ant-typography").last

            if value_elem.count() > 0 and label_elem.count() > 0:
                val = value_elem.inner_text().strip()
                lab = label_elem.inner_text().strip().lower()
                results[lab] = val
    except Exception:
        pass
    return results


# DEF: Liest Release-Date, Label, Album etc.
def _extract_metadata(page: Page) -> dict:
    """SECTION: META - Liest "Key: Value"-Paare aus dem ._4aYzP-Container."""
    results: dict = {}
    try:
        meta_container = page.locator("._4aYzP")
        if meta_container.count() == 0:
            return results
        meta_items = meta_container.locator("div")
        for i in range(meta_items.count()):
            text = meta_items.nth(i).inner_text().strip()
            if ":" not in text:
                continue
            label_part, _, value_part = text.partition(":")
            lab = label_part.strip().lower().replace(" ", "_")
            val = value_part.strip()
            if lab and val:
                results[lab] = val
    except Exception:
        pass
    return results


# DEF: Sucht den direkten Songstats-Link
def _extract_songstats_url(page: Page) -> str | None:
    """SECTION: CROSS-LINK - Liest den Songstats-Direktlink (falls vorhanden).

    Anker des Links wird mit `?source=overview` versehen, damit Songstats
    nicht auf Spotify weiterleitet.
    """
    try:
        link = page.locator("a[aria-label='Songstats']")
        if link.count() == 0:
            return None
        href = link.first.get_attribute("href")
        if not href:
            return None
        return f"{href.split('?')[0]}?source=overview"
    except Exception:
        return None


# DEF: Aggregiert alle Sektionen zu einem formatierten Resultat
def extract_song_data(page: Page, song: str, artists: list[str]) -> dict:
    """ENTRY: Liest alle relevanten Datenpunkte einer Tunebat-Song-Seite.

    Voraussetzung: ``.yIPfN`` ist sichtbar (Song-Seite vollständig geladen).

    Args:
        page: Playwright-Page nach Klick auf das beste Suchergebnis.
        song: Original-Songname (für ``title``).
        artists: Artist-Liste (für ``artist``).

    Returns:
        Dictionary ohne None-Werte. Audio-Features liegen unter
        ``audio_features`` als verschachteltes dict.
    """
    log_status("🔍 Extrahiere Metriken...")
    raw: dict = {}
    raw.update(_extract_metrics(page))
    raw.update(_extract_progress_metrics(page))
    raw.update(_extract_metadata(page))

    songstats_url = _extract_songstats_url(page)

    formatted = {
        "url": page.url,
        "title": song,
        "artist": ", ".join(artists),
        "key": raw.get("key"),
        "camelot": raw.get("camelot"),
        "bpm": raw.get("bpm"),
        "duration": raw.get("duration"),
        "popularity": raw.get("popularity"),
        "release_date": raw.get("release_date"),
        "explicit": raw.get("explicit"),
        "album": raw.get("album"),
        "label": raw.get("label"),
        "audio_features": {k: raw[k] for k in AUDIO_FEATURE_KEYS if k in raw},
        "songstats_url": songstats_url,
    }
    formatted = {k: v for k, v in formatted.items() if v is not None}
    log_status("✅ Daten extrahiert.")
    return formatted
