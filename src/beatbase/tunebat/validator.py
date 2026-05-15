import difflib

from beatbase.tunebat.config import ARTIST_BONUS


# DEF: calculate_validation_score(found_text, target_string, artists) -> float
def calculate_validation_score(found_text: str, target_string: str, artists: list[str]) -> float:
    """Bewertet, wie gut ein Suchergebnis zum gesuchten Song passt.

    Args:
        found_text: Der Text des gefundenen Suchergebnisses.
        target_string: Der zusammengesetzte Zielstring (Titel + Künstler).
        artists: Liste der erwarteten Künstler.

    Returns:
        Ein Float-Score, wobei höhere Werte einen besseren Match bedeuten.
    """
    found_lower = found_text.lower()
    score = difflib.SequenceMatcher(None, target_string.lower(), found_lower).ratio()
    for artist in artists:
        if artist.lower() in found_lower:
            score += ARTIST_BONUS

    if "edit" in found_lower or "remix" in found_lower:
        score += 0.1
    return score
