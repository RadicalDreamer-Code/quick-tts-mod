"""Shared helpers used by every TTS backend."""

import re


class Interrupted(Exception):
    """Raised when a caller stopped an in-progress speak()/save() via interrupt()."""


# Lines that are only punctuation/underscores can't be synthesized (the local
# vocoder's conv layers need a minimum-length input) and aren't real text
# anyway — drop them before they ever reach any backend.
_JUNK_LINE_RE = re.compile(r"^[\W_]+$", re.UNICODE)


def sanitize(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip() and not _JUNK_LINE_RE.match(ln.strip())]
    return "\n".join(lines).strip()
