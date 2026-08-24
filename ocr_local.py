"""Local OCR via Tesseract (offline, default)."""

import pytesseract
from PIL import Image


def extract_text(image_path: str) -> str:
    image = Image.open(image_path)
    return pytesseract.image_to_string(image).strip()
