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

    def to_dict(self) -> dict:
        """Plain JSON form, so a slow model run can be cached and re-scored."""
        return {
            "items": [
                {
                    "text": item.text,
                    "confidence": item.confidence,
                    "bbox": item.bbox.model_dump() if item.bbox else None,
                    "hint": item.hint,
                }
                for item in self.items
            ],
            "title_hint": self.title_hint,
            "backend": self.backend,
            "seconds": self.seconds,
            "truncated": self.truncated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RawExtraction:
        items = [
            RawItem(
                text=item["text"],
                confidence=item.get("confidence"),
                bbox=BBox(**item["bbox"]) if item.get("bbox") else None,
                hint=item.get("hint"),
            )
            for item in data.get("items", [])
        ]
        return cls(
            items=items,
            title_hint=data.get("title_hint"),
            backend=data.get("backend", "unknown"),
            seconds=data.get("seconds", 0.0),
            truncated=data.get("truncated", False),
        )


class Extractor(Protocol):
    name: str

    def extract(self, image: Image.Image) -> RawExtraction: ...
