"""OCR via Claude vision (on-demand, for images Tesseract handles poorly)."""

import base64
import mimetypes
import os

import anthropic

MODEL = "claude-haiku-4-5"

_client: anthropic.Anthropic | None = None


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def extract_text(image_path: str) -> str:
    media_type = mimetypes.guess_type(image_path)[0] or "image/png"
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Transcribe all text visible in this image verbatim. "
                            "Output only the transcribed text, with no commentary, "
                            "preamble, or added formatting. If there is no text, "
                            "output nothing."
                        ),
                    },
                ],
            }
        ],
    )

    return "".join(block.text for block in response.content if block.type == "text").strip()
