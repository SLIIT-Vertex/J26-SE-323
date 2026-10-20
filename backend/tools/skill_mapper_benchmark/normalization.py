"""Deterministic mathematical-notation normalization; words and scripts are left untouched."""

import re
import unicodedata

_VULGAR_FRACTIONS = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅕": "1/5", "⅖": "2/5",
    "⅗": "3/5", "⅘": "4/5", "⅙": "1/6", "⅚": "5/6", "⅐": "1/7", "⅛": "1/8", "⅜": "3/8",
    "⅝": "5/8", "⅞": "7/8", "⅑": "1/9", "⅒": "1/10",
}  # fmt: skip
_SYMBOLS = str.maketrans(
    {
        "⁄": "/",  # fraction slash
        "∕": "/",  # division slash
        "−": "-",  # minus sign
        "–": "-",
        "—": "-",
        "∗": "*",
        "＋": "+",
        "＝": "=",
        "：": ":",
        **{chr(0xFF10 + digit): str(digit) for digit in range(10)},  # full-width digits
    }
)
_SPACED_SLASH = re.compile(r"(?<=\d)\s*/\s*(?=\d)")
_SPACED_COLON = re.compile(r"(?<=\d)\s*:\s*(?=\d{2}\b)")


def normalize_math_text(text: str) -> str:
    """Canonicalize notation (½ → 1/2, 1 / 4 → 1/4, − → -) without translating or respelling."""

    normalized = unicodedata.normalize("NFC", text).translate(_SYMBOLS)
    for glyph, fraction in _VULGAR_FRACTIONS.items():
        normalized = re.sub(rf"(?<=\d){glyph}", f" {fraction}", normalized)
        normalized = normalized.replace(glyph, fraction)
    normalized = _SPACED_SLASH.sub("/", normalized)
    normalized = _SPACED_COLON.sub(":", normalized)
    return " ".join(normalized.split())
