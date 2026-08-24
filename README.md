# quick-tts-mod

Drag an image containing text onto the window; it gets OCR'd and read aloud
via [Coqui TTS](https://github.com/coqui-ai/tts).

- OCR runs via a local [GLM-OCR](https://ollama.com/library/glm-ocr) model
  served through [Ollama](https://ollama.com) — no cloud calls, no API key.
  A "Re-run OCR" button re-reads the same image if the first pass came out
  wrong.
- Text is shown in an editable box before speaking, so OCR mistakes can be
  fixed by hand.
- TTS uses the VITS model and runs on GPU if a CUDA device is available
  (falls back to CPU automatically otherwise — just slower).
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

## Run

```bash
.venv/bin/python main.py
```
