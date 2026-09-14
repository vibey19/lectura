"""Canonical note representation.

This is the single source of truth for a processed lecture image. Renderers,
exporters and the editor all operate on this model; nothing downstream is
allowed to invent its own shape.

Two invariants matter more than anything else here:

1. ``Block.origin`` records where content came from. Extracted content is what
   the source image actually showed; supplements are generated additions the
   user opted into. They are never silently merged.
2. ``Block.bbox`` points back into the source image so the UI can always show
   the user what a block was derived from.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.1"


class Origin(StrEnum):
    """Where a block's content came from. See invariant 1 above."""

    EXTRACTED = "extracted"   # read off the source image
    SUPPLEMENT = "supplement"  # model-generated, user-accepted
    USER = "user"             # typed or edited by the user


class BlockType(StrEnum):
    HEADING = "heading"
    TEXT = "text"
    EQUATION = "equation"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    DEFINITION = "definition"
    TABLE = "table"
    DIAGRAM = "diagram"
    CODE = "code"


class Flag(StrEnum):
    """Verification warnings. These describe doubt, never a correction."""

    LOW_CONFIDENCE = "low_confidence"
    INVALID_LATEX = "invalid_latex"
    PARTIALLY_OCCLUDED = "partially_occluded"
    AMBIGUOUS = "ambiguous"


class BBox(BaseModel):
    """Normalised (0-1) box into the source image, origin top-left."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class Block(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: BlockType
    content: str = ""
    items: list[str] = Field(default_factory=list)   # bullet/numbered lists
    level: int | None = None                          # headings: 1-6
    origin: Origin = Origin.EXTRACTED
    confidence: float | None = Field(default=None, ge=0, le=1)
    bbox: BBox | None = None
    source_image: str | None = None
    flags: list[Flag] = Field(default_factory=list)
    reviewed: bool = False
    """A person checked this block against the source and accepted it as read.

    Separate from origin on purpose. Confirming a transcription is not writing
    it: the content is still what came off the page, and the model's confidence
    and flags still describe the model. Before this existed, the only way to
    clear a warning was to save the block unchanged, which relabelled extracted
    text as user-authored and threw the confidence away.
    """

    def is_uncertain(self, threshold: float = 0.75) -> bool:
        """True when the editor should surface this block for review first."""
        if self.reviewed:
            return False
        if self.flags:
            return True
        return self.confidence is not None and self.confidence < threshold


class Note(BaseModel):
    schema_version: str = SCHEMA_VERSION
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_images: list[str] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)

    def extracted(self) -> list[Block]:
        return [b for b in self.blocks if b.origin is Origin.EXTRACTED]

    def supplements(self) -> list[Block]:
        return [b for b in self.blocks if b.origin is Origin.SUPPLEMENT]

    def needs_review(self, threshold: float = 0.75) -> list[Block]:
        return [b for b in self.blocks if b.is_uncertain(threshold)]
