# quick-tts-mod

Drag an image containing text onto the window; it gets OCR'd and read aloud.

- OCR runs via a local [GLM-OCR](https://ollama.com/library/glm-ocr) model
  served through [Ollama](https://ollama.com) — no cloud calls, no API key.
  A "Re-run OCR" button re-reads the same image if the first pass came out
  wrong.
- Text is shown in an editable box before speaking, so OCR mistakes can be
  fixed by hand.
- Two swappable TTS backends, picked from the "Voice" dropdown:
  - **Local (GPU)** — [Coqui TTS](https://github.com/coqui-ai/tts) (VITS),
    fully offline. Runs on GPU if a CUDA device is available, falls back to
    CPU otherwise.
  - **ElevenLabs (Cloud)** — needs `ELEVENLABS_API_KEY` (and a `voice_id`
    your account actually has access to — see below) set via environment
    variable or a `.env` file in the project root (gitignored, loaded
    automatically at startup).
- A "Stop" button interrupts an in-progress OCR/synthesis call or playback.

## Setup

Requires Python ≤3.12 (Coqui TTS doesn't support 3.13+ yet). This repo uses
[uv](https://docs.astral.sh/uv/) to manage an isolated 3.11 environment:

```bash
uv venv --python 3.11 .venv
uv pip install -p .venv -r requirements.txt
```

Make sure [Ollama](https://ollama.com) is running and the OCR model is
pulled:

```bash
ollama pull glm-ocr
```

For the ElevenLabs voice, create a `.env` file (see `.env.example`):

```
ELEVENLABS_API_KEY=your-key-here
ELEVENLABS_VOICE_ID=your-voice-id   # optional, defaults to a preset
ELEVENLABS_MODEL_ID=eleven_turbo_v2_5   # optional
```

Free-tier ElevenLabs accounts can't use library/shared voices via the API
(`402 paid_plan_required`) — `ELEVENLABS_VOICE_ID` needs to point at a voice
your account actually owns (cloned or Voice Design), or the plan needs
upgrading.

## Run

```bash
.venv/bin/python main.py
```
