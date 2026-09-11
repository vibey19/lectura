"""Extractor interface.

Every extraction backend returns the same thing: raw transcribed items with
optional confidence. Turning those into typed blocks is `structure.py`'s job,
deliberately kept separate — see ARCHITECTURE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from PIL import Image

from lectura.schema import BBox


class ExtractionError(RuntimeError):
    """Extraction produced nothing usable.

    Raised rather than returning an empty result: a blank page presented as a
    successful read is the worst outcome, because the user waits minutes and is
    given no reason and nothing to act on.
    """


@dataclass
class RawItem:
    """One transcribed chunk, before document structure is inferred."""

    text: str
    confidence: float | None = None
    bbox: BBox | None = None
    hint: str | None = None   # backend's guess at type; advisory only


@dataclass
class RawExtraction:
    items: list[RawItem] = field(default_factory=list)
    title_hint: str | None = None
    backend: str = "unknown"
    seconds: float = 0.0
    truncated: bool = False   # the model hit its output limit mid-answer


class Extractor(Protocol):
    name: str

    def extract(self, image: Image.Image) -> RawExtraction: ...
