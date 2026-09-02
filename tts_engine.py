"""Dispatches text-to-speech calls to whichever backend is currently selected."""

import tts_elevenlabs
import tts_local
from tts_common import Interrupted, sanitize  # noqa: F401 - re-exported for callers

BACKENDS = {
    "local": tts_local,
    "elevenlabs": tts_elevenlabs,
}
BACKEND_LABELS = {
    "local": "Local (GPU)",
    "elevenlabs": "ElevenLabs (Cloud)",
}

_current = "local"


def set_backend(name: str) -> None:
    global _current
    if name not in BACKENDS:
        raise ValueError(f"Unknown TTS backend: {name}")
    _current = name


def current_backend() -> str:
    return _current


def available(name: str | None = None) -> bool:
    return BACKENDS[name or _current].available()


def speak(text: str) -> None:
    BACKENDS[_current].speak(text)


def save(text: str, out_path: str) -> None:
    BACKENDS[_current].save(text, out_path)


def interrupt() -> None:
    BACKENDS[_current].interrupt()
