"""IPC-Layer für den aktuell spielenden Song.

Liest und schreibt je nach `core/config.py::IPC_MODE` entweder eine Datei
oder die Windows-User-Umgebungsvariable.
"""

import json
import os
import subprocess

from beatbase.shared.config import ENV_VAR_NOW_PLAY, IPC_FILE_PATH, IPC_MODE, SENTINEL_NONE


# DEF: Liest den aktuellen Song als strukturiertes Dictionary
def read_now_playing_data() -> dict:
    """Gibt den aktuellen Track als Dict {song, artists} zurück."""
    raw = ""
    if IPC_MODE == "file":
        raw = _read_file()
    elif IPC_MODE == "env":
        raw = _read_env()

    if not raw or raw == SENTINEL_NONE:
        return {"song": None, "artists": []}

    try:
        # Versuch als JSON zu parsen
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback für altes Format "Song von Artist"
        if " von " in raw:
            parts = raw.split(" von ")
            return {"song": parts[0].strip(), "artists": [parts[1].strip()]}
        return {"song": raw, "artists": []}


# DEF: Liest den aktuellen Song (Kompatibilitäts-Wrapper)
def read_now_playing() -> str:
    """Gibt den Song als String zurück (für Abwärtskompatibilität)."""
    data = read_now_playing_data()
    if not data["song"]:
        return SENTINEL_NONE
    if data["artists"]:
        return f"{data['song']} von {', '.join(data['artists'])}"
    return data["song"]


# DEF: Schreibt den aktuellen Song strukturiert
def write_now_playing(song: str, artists: list[str] = None) -> None:
    """Setzt den aktuellen Song strukturiert im IPC-Layer."""
    data = {"song": song, "artists": artists or []}
    value = json.dumps(data, ensure_ascii=False)

    if IPC_MODE == "file":
        _write_file(value)
    elif IPC_MODE == "env":
        _write_env(value)


# DEF: Setzt den Sentinel-Wert "kein Song"
def clear_now_playing() -> None:
    """Signalisiert allen Lesern: kein Track aktiv."""
    if IPC_MODE == "file":
        _write_file(SENTINEL_NONE)
    elif IPC_MODE == "env":
        _write_env(SENTINEL_NONE)


def _read_file() -> str:
    path = os.path.join(os.getcwd(), IPC_FILE_PATH)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _write_file(value: str) -> None:
    # WHY: Atomares Schreiben (temp + replace) verhindert Partial-Reads.
    path = os.path.join(os.getcwd(), IPC_FILE_PATH)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(value)
    os.replace(tmp, path)


def _read_env() -> str:
    cmd = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; [System.Environment]::GetEnvironmentVariable('{ENV_VAR_NOW_PLAY}', 'User')"
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _write_env(value: str) -> None:
    safe = value.replace("'", "''")
    cmd = f"[System.Environment]::SetEnvironmentVariable('{ENV_VAR_NOW_PLAY}', '{safe}', 'User')"
    subprocess.run(["powershell", "-Command", cmd], capture_output=True)
