"""Text-to-speech via the ElevenLabs cloud API.

Requests raw PCM audio directly (pcm_24000) instead of MP3, so playback and
saving reuse the exact same numpy/sounddevice path as the local engine —
no mp3 decoder dependency needed.

Playback interruption uses the same same-thread poll-and-stop pattern as
tts_local (see that module's docstring for why cross-thread sd.stop() is
unreliable here).
"""

import os
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf
from elevenlabs.client import ElevenLabs

from tts_common import Interrupted, sanitize  # noqa: F401 - re-exported for callers

MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "be5BqjdCBGa7uaJYeTl5")
OUTPUT_FORMAT = "pcm_24000"
SAMPLE_RATE = 24000

_client: ElevenLabs | None = None
_stop_playback = threading.Event()


def available() -> bool:
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        _client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    return _client


def _synthesize(text: str) -> np.ndarray:
    text = sanitize(text)
    if not text:
        raise ValueError("There's no speakable text left after removing empty/junk content.")

    result = _get_client().text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
        output_format=OUTPUT_FORMAT,
    )
    # The SDK returns either raw bytes or an iterator of byte chunks
    # depending on version — handle both.
    raw = bytes(result) if isinstance(result, (bytes, bytearray)) else b"".join(result)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def speak(text: str) -> None:
    wav = _synthesize(text)
    _stop_playback.clear()
    sd.play(wav, samplerate=SAMPLE_RATE)
    while sd.get_stream().active:
        if _stop_playback.is_set():
            sd.stop()
            break
        time.sleep(0.02)


def save(text: str, out_path: str) -> None:
    wav = _synthesize(text)
    sf.write(out_path, wav, SAMPLE_RATE)


def interrupt() -> None:
    """Stop any playing audio. (There's no in-flight synthesis to abort here —
    a convert() call is a single HTTP request, not a long-running process.)"""
    _stop_playback.set()
