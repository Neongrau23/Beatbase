from bs4 import BeautifulSoup

from beatbase.songstats.browser.navigator import find_song_profile
from beatbase.songstats.scraper.overview import _extract_overview
from beatbase.utils.log import log_status
from beatbase.utils.search_variations import extract_featured_artists, generate_variations


# DEF: run_songstats_extraction(page, target_song, target_artists) -> dict
def run_songstats_extraction(page, target_song: str, target_artists: list[str]) -> dict:
    """Hauptkoordinator für die Datenbeschaffung eines Songs.

    Fokus: NUR Overview-Sektion. Keine Unterseiten (Spotify/Shazam), keine Hover-Metriken.
    """
    # Versteckte Künstler aus dem Titel extrahieren und zur Liste hinzufügen
    featured = extract_featured_artists(target_song)
    for artist in featured:
        if not any(artist.lower() in existing.lower() for existing in target_artists):
            target_artists.append(artist)

    log_status(f"\n🔍 Songstats-Suche: {target_song} von {', '.join(target_artists)}")
    target_string = f"{target_song} {', '.join(target_artists)}".lower()
    queries = generate_variations(target_song, target_artists)
    final_data = {}

    if find_song_profile(page, queries, target_string, target_artists):
        try:
            page.wait_for_load_state("networkidle")

            # Stelle sicher, dass wir auf der 'Overview'-Ansicht sind
            # Wir verzichten auf teure Mouse-Hovers und Unterseiten-Klicks.
            if "source=" not in page.url or "source=overview" not in page.url:
                page.goto(
                    f"{page.url.split('?')[0]}?source=overview",
                    wait_until="networkidle",
                )

            soup = BeautifulSoup(page.content(), "html.parser")
            final_data = _extract_overview(soup)

            # Die Profil-URL hinzufügen (ohne Query-Parameter)
            final_data["url"] = page.url.split("?")[0]

            if final_data:
                log_status("\n  📊 Extrahierte Details (Overview):")
                for k, v in final_data.items():
                    log_status(f"    -> {str(k).ljust(25)}: {v}")
            else:
                log_status("\n  ⚠️ Keine Daten in der Overview gefunden.")

        except Exception as e:
            log_status(f"  ❌ Extraktions-Fehler: {e}")
    else:
        log_status("  ❌ Kein Treffer.")

    return final_data
