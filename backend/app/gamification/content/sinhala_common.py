"""Pieces shared by the Sinhala game packages: opaque ids, Model 1 and Model 2 references.

Each package owns its source, items, rubric and copy. What is identical across packages, and
must stay identical so the research can compare them, lives here.
"""

from __future__ import annotations

import hashlib
import unicodedata

UNKNOWN = "unknown_or_other"
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
DONE_LINE = "දැන් ඔයාම කරලා බලන්න! 💪"
UNKNOWN_CODE_MAPPING = {
    "mapping_version": "g5-sin-unknown-reconciliation-v1",
    "package_code": UNKNOWN,
    "shared_code": "unknown_or_other",
}


class SinhalaResponseError(ValueError):
    """A response the server refuses to score. ``code`` is machine-readable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def digest(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def token(prefix: str, value: object, salt: str) -> str:
    """An opaque presentation-local id: it never encodes position or correctness."""

    return f"{prefix}-{hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:12]}"


