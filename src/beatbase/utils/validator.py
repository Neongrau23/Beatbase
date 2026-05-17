"""Zentrales Scoring für Suchergebnisse.

Bewertet, wie gut ein gefundener Text zum gesuchten Song passt.
"""

import difflib


# DEF: calculate_validation_score(found_text, target_string, artists, artist_bonus) -> float
def calculate_validation_score(found_text: str, target_string: str, artists: list[str], artist_bonus: float = 0.2) -> float:
    """SECTION: SCORING - Bewertet, wie gut ein Suchergebnis zum gesuchten Song passt.

    Nutzt Fuzzy-Matching zwischen Zielstring und gefundenem Text und
    vergibt einen Bonus für jeden erkannten Künstler sowie für bestimmte Keywords.

    Args:
        found_text: Der Text des gefundenen Suchergebnisses.
        target_string: Der zusammengesetzte Zielstring (Titel + Künstler).
        artists: Liste der erwarteten Künstler.
        artist_bonus: Bonus, der für jeden gefundenen Künstler aufgeschlagen wird.

    Returns:
        Ein Float-Score, wobei höhere Werte einen besseren Match bedeuten.
    """
    found_text = found_text.lower()
    score = difflib.SequenceMatcher(None, target_string.lower(), found_text).ratio()

    for artist in artists:
        if artist.lower() in found_text:
            score += artist_bonus

    # Leichter Bonus für Edits/Remixe, um Instrumentals oder Cover abzuwerten
    if "edit" in found_text or "remix" in found_text:
        score += 0.1

    return score
