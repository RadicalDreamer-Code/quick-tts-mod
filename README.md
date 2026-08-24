# quick-tts-mod

Drag an image containing text onto the window; it gets OCR'd and read aloud
via [Coqui TTS](https://github.com/coqui-ai/tts).

- OCR defaults to local, offline Tesseract. A "Re-OCR with Claude" button
  re-reads the image via Claude vision for cases Tesseract struggles with
  (skewed photos, handwriting, stylized fonts).
- Text is shown in an editable box before speaking, so OCR mistakes can be
  fixed by hand.

## Setup

Requires Python ≤3.12 (Coqui TTS doesn't support 3.13+ yet). This repo uses
[uv](https://docs.astral.sh/uv/) to manage an isolated 3.11 environment:

```bash
uv venv --python 3.11 .venv
uv pip install -p .venv -r requirements.txt
```

System dependencies (Arch/CachyOS):

```bash
sudo pacman -S tesseract tesseract-data-eng
```

For the Claude vision re-OCR button, set an API key:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

## Run

```bash
.venv/bin/python main.py
```
