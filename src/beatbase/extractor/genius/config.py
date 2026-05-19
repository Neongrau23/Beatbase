# CONFIG: Genius-spezifische Konfiguration

BASE_URL = "https://genius.com"
PROFILE_DIR = "../.profiles/genius_profile_playwright"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
WEBDRIVER_TIMEOUT = 15
PAGE_LOAD_SLEEP = 0.5
HEADLESS = True

# Validation Constants
MATCH_THRESHOLD = 0.8

# CONFIG: Pro Artist-Profil "Show all songs" oeffnen und in genius.db sammeln.
# WHY: Lyrics-Pfad ist schnell; die Artist-Sammlung kostet pro beteiligtem
# Kuenstler einen Profil-Load + langes Scrollen. Auf False setzen, wenn nur
# Lyrics/Credits gebraucht werden.
COLLECT_ARTIST_SONGS = True
