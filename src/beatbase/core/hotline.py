# SECTION: HOTLINE - Der nackte Datenspeicher
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hotline:
    """
    ENTRY: Speichert alle Variablen des Prozesses in ihrer Rohform.
    Keine Logik, keine Strukturierung - nur Ablage.
    """

    storage: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set(self, source: str, key: str, value: Any):
        """Legt einen Wert nackt im Speicher ab."""
        if source not in self.storage:
            self.storage[source] = {}
        self.storage[source][key] = value

    def get(self, source: str, key: str, default: Any = "kein anschluss unter dieser variable...") -> Any:
        """Holt einen spezifischen Rohwert. Standard-Fehlermeldung bei Fehlen."""
        source_data = self.storage.get(source, {})
        if key not in source_data:
            return default
        return source_data[key]

    def get_all(self) -> dict:
        """Gibt den gesamten Speicher für Builder-Funktionen aus."""
        return self.storage

    def clear(self) -> None:
        """Leert den Speicher. Notwendig zwischen Songs im Watcher-Loop."""
        self.storage = {}


# BRIDGE: Die globale Instanz
bus = Hotline()
