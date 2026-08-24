"""Text-to-speech via Coqui TTS."""

import sounddevice as sd
import soundfile as sf
from TTS.api import TTS

MODEL_NAME = "tts_models/en/ljspeech/tacotron2-DDC"

_tts: TTS | None = None


def _get_tts() -> TTS:
    global _tts
    if _tts is None:
        _tts = TTS(model_name=MODEL_NAME, progress_bar=False, gpu=False)
    return _tts


def speak(text: str) -> None:
    tts = _get_tts()
    wav = tts.tts(text=text)
    sd.play(wav, samplerate=tts.synthesizer.output_sample_rate)
    sd.wait()


def save(text: str, out_path: str) -> None:
    tts = _get_tts()
    tts.tts_to_file(text=text, file_path=out_path)
