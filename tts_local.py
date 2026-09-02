"""Text-to-speech via Coqui TTS (GPU-accelerated VITS, fully local/offline).

Synthesis runs in a persistent worker subprocess: the underlying model can
segfault or abort natively on certain malformed input (very short or
punctuation-only fragments), and a crash there must not take the whole GUI
process down with it. If the worker dies, it's respawned on the next call.

Playback interruption polls instead of blocking on sd.wait(): calling
sd.stop() from a different thread than the one that called sd.play() is
"supported" by the sounddevice API, but proved unreliable here — after a few
play/stop cycles from separate threads, sd.wait() would hang forever (and
once, crashed the whole process with a PortAudio mutex assertion). Only ever
calling sd.stop() from the same thread that called sd.play() avoided both.
"""

import multiprocessing as mp
import threading
import time

import sounddevice as sd

from tts_common import Interrupted, sanitize

MODEL_NAME = "tts_models/en/ljspeech/vits"

_ctx = mp.get_context("spawn")
_process: mp.Process | None = None
_parent_conn = None
_interrupted = False
_busy = False  # True only while a synthesis request is in flight
_stop_playback = threading.Event()


def available() -> bool:
    return True


def _worker_main(conn):
    import torch
    from TTS.api import TTS

    tts = TTS(model_name=MODEL_NAME, progress_bar=False)
    tts.to("cuda" if torch.cuda.is_available() else "cpu")
    while True:
        try:
            message = conn.recv()
        except EOFError:
            return
        if message is None:
            return
        action, text, out_path = message
        try:
            if action == "speak":
                wav = tts.tts(text=text)
                conn.send(("ok", wav, tts.synthesizer.output_sample_rate))
            else:
                tts.tts_to_file(text=text, file_path=out_path)
                conn.send(("ok", None, None))
        except Exception as exc:  # noqa: BLE001 - reported back to the caller
            conn.send(("error", str(exc), None))


def _ensure_worker():
    global _process, _parent_conn
    if _process is None or not _process.is_alive():
        _parent_conn, child_conn = _ctx.Pipe()
        _process = _ctx.Process(target=_worker_main, args=(child_conn,), daemon=True)
        _process.start()


def _request(action: str, text: str, out_path: str | None = None):
    text = sanitize(text)
    if not text:
        raise ValueError("There's no speakable text left after removing empty/junk content.")

    global _busy
    _ensure_worker()
    _busy = True
    try:
        _parent_conn.send((action, text, out_path))
        try:
            status, payload, extra = _parent_conn.recv()
        except (EOFError, OSError):
            global _process, _interrupted
            exitcode = _process.exitcode if _process is not None else None
            _process = None  # respawn on next call
            if _interrupted:
                _interrupted = False
                raise Interrupted("Stopped.")
            raise RuntimeError(
                f"Speech synthesis crashed (worker exit code {exitcode}). "
                "Try editing the text — a leftover OCR artifact may have confused the model."
            )
    finally:
        _busy = False
    if status == "error":
        raise RuntimeError(payload)
    return payload, extra


def interrupt() -> None:
    """Stop any playing audio and abort an in-progress speak()/save() call."""
    global _interrupted
    _stop_playback.set()  # picked up by speak()'s own polling loop
    if _busy and _process is not None and _process.is_alive():
        _interrupted = True
        _process.terminate()
        _process.join(timeout=2)


def speak(text: str) -> None:
    wav, sample_rate = _request("speak", text)
    _stop_playback.clear()
    sd.play(wav, samplerate=sample_rate)
    # Poll rather than sd.wait(): sd.stop() must be called from this same
    # thread (see module docstring) for interruption to be reliable.
    while sd.get_stream().active:
        if _stop_playback.is_set():
            sd.stop()
            break
        time.sleep(0.02)


def save(text: str, out_path: str) -> None:
    _request("save", text, out_path)
