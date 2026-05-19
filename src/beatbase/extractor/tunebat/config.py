# CONFIG: Tunebat-spezifische Konfiguration

# Profil-Verzeichnis fuer Playwright. Relativ zu src/.
# Wenn du ein echtes Chrome-Profil verwendest (siehe README/Notiz), zeige hier darauf:
#   PROFILE_DIR = "../.profiles/tunebat_real"
# und setze USE_STEALTH = False — Stealth auf einem echten Profil sieht inkonsistent aus.
PROFILE_DIR = "../.profiles/tunebat_profile"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
HEADLESS = True
MATCH_THRESHOLD = 0.8

# playwright-stealth aktivieren? Bei einem frisch hochgezogenen Profil hilft Stealth,
# auf einem echten/warmen Chrome-Profil ist es eher kontraproduktiv (sichtbarer Fingerprint).
USE_STEALTH = True
