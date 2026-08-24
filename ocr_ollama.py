"""OCR via a local GLM-OCR model through Ollama (on-demand, for images Tesseract handles poorly)."""

import re

import ollama

MODEL = "glm-ocr"

PROMPT = (
    "Transcribe all text visible in this image verbatim. Output only the "
    "transcribed text, with no commentary, preamble, or added formatting. "
    "If there is no text, output nothing."
)

_FENCE_RE = re.compile(r"```\w*")
# Lines that are only punctuation/underscores, e.g. "---", "___", "?", "**" —
# markdown separators or fence debris, never real transcribed content.
_JUNK_LINE_RE = re.compile(r"^[\W_]+$", re.UNICODE)
_QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def available() -> bool:
    try:
        models = ollama.list().models
    except Exception:
        return False
    return any(m.model.split(":")[0] == MODEL for m in models)


def _normalize(line: str) -> str:
    return line.strip().translate(_QUOTE_MAP).casefold()


def _dedupe_repeated_block(lines: list[str]) -> list[str]:
    """This model sometimes re-emits its whole answer one or more times in a
    row after getting it right once. Find the shortest leading block that
    repeats immediately and keep just the first copy."""
    normalized = [_normalize(ln) for ln in lines]
    n = len(lines)
    for block_len in range(1, n // 2 + 1):
        if normalized[:block_len] == normalized[block_len : 2 * block_len]:
            return lines[:block_len]
    # Fallback for a repeat that got cut off mid-second-copy (e.g. by
    # num_predict): if the very first line reappears later, that's almost
    # always the start of a repeat, not real content repeating a heading.
    if n > 1:
        first = normalized[0]
        for i in range(1, n):
            if normalized[i] == first:
                return lines[:i]
    return lines


def _clean(text: str) -> str:
    """Strip markdown code fences, separator debris, and the repetition
    loops this model occasionally falls into after the real answer."""
    lines = [
        ln
        for ln in text.splitlines()
        if ln.strip()
        and not _FENCE_RE.fullmatch(ln.strip())
        and not _JUNK_LINE_RE.match(ln.strip())
    ]
    deduped = []
    for line in lines:
        if deduped and _normalize(deduped[-1]) == _normalize(line):
            continue
        deduped.append(line)
    deduped = _dedupe_repeated_block(deduped)
    return "\n".join(deduped).strip()


def extract_text(image_path: str) -> str:
    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": PROMPT,
                "images": [image_path],
            }
        ],
        options={"repeat_penalty": 1.3, "num_predict": 2048},
    )
    return _clean(response["message"]["content"])
