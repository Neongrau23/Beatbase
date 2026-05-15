"""Holt den aktuell spielenden Song von Spotify inklusive Metadaten."""

import os

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from beatbase.utils.now_playing import clear_now_playing, write_now_playing

# CONFIG: Spotify API Scopes
SCOPE = "user-read-currently-playing"


def get_current_spotify_track() -> dict | None:
    """Holt Track, Artists, ISRC und Release Date von Spotify."""
    load_dotenv()

    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")

    if not client_id or not client_secret:
        print("Fehler: Spotify API Credentials fehlen in der .env Datei.")
        return None

    # Cache im selben Ordner wie das Skript speichern, damit der Token gefunden wird
    cache_path = os.path.join(os.path.dirname(__file__), ".spotify_cache")

    # STATE: Initialisiere den Spotify Client
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=SCOPE,
            cache_path=cache_path,
        )
    )

    # BRIDGE: Frage die API nach dem aktuellen Track
    try:
        current_track = sp.current_user_playing_track()
    except Exception as e:
        print(f"Fehler beim Abrufen des Spotify-Tracks: {e}")
        return None

    if current_track is not None and current_track.get("is_playing"):
        item = current_track["item"]
        return {
            "id": item["id"],
            "song": item["name"],
            "artists": [artist["name"] for artist in item["artists"]],
            "isrc": item.get("external_ids", {}).get("isrc"),
            "release_date": item.get("album", {}).get("release_date"),
            "spotify_url": item.get("external_urls", {}).get("spotify"),
        }
    else:
        return None


if __name__ == "__main__":
    track_info = get_current_spotify_track()
    if track_info:
        track_name = track_info["song"]
        artists_str = ", ".join(track_info["artists"])
        # Format wird von songstats/genius als Suchbegriff genutzt ("Title von Artists")
        full_now_play = f"{track_name} von {artists_str}"

        print(f"🎵 Aktuell spielt: {full_now_play}")
        write_now_playing(full_now_play)
    else:
        print("⏸️ Aktuell wird kein Song auf Spotify abgespielt.")
        clear_now_playing()
