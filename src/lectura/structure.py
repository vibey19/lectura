"""Turn raw transcribed lines into typed blocks.

Kept separate from extraction on purpose. Measured on real lecture photos, the
VLM transcribed well but typed blocks badly - three-line LaTeX derivations came
back as plain text, and numbered lists arrived shattered into loose lines. This
stage operates on text alone, so it is deterministic, unit-testable, and fixable
without touching the vision model.
"""

from __future__ import annotations

import re

from lectura.extract.base import RawExtraction, RawItem
from lectura.schema import Block, BlockType, Flag, Note

# A line is mathematical if it is mostly notation rather than prose.
_MATH_DELIM = re.compile(r"\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]", re.DOTALL)
_MATH_CMD = re.compile(
    r"\\(frac|sqrt|sum|int|beta|alpha|mu|sigma|begin"
    r"|partial|cdot|times|vec|mathbb|hat)"
)
_BULLET = re.compile(r"^\s*[-*•‣●◦>→]\s+(.*)")
_NUMBERED = re.compile(r"^\s*(\d+)[.)]\s+(.*)")
_HEADING_HASH = re.compile(r"^\s*(#+)\s*(.*)")


def _strip_math_delims(text: str) -> str:
    """Unwrap math delimiters so KaTeX receives bare LaTeX.

    Lines often arrive labelled - "a) $\\sqrt{x}$" - so the delimiters cannot be
    assumed to span the whole line. Any prefix is kept; only the wrappers go.
    """

    def unwrap(match: re.Match[str]) -> str:
        return next(g for g in match.groups() if g is not None).strip()

    return _MATH_DELIM.sub(unwrap, text.strip()).strip()


def _is_math(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _MATH_DELIM.fullmatch(stripped):
        return True
    if _MATH_CMD.search(stripped):
        # Prose mentioning one symbol is not an equation; notation-dense is.
        words = re.findall(r"[A-Za-z]{4,}", re.sub(_MATH_CMD, "", stripped))
        return len(words) <= 3
    # Bare arithmetic such as "2x - y = 0"
    if "=" in stripped and len(stripped) < 60:
        letters = sum(c.isalpha() for c in stripped)
        return letters <= max(4, len(stripped) // 4)
    return False


def _looks_like_heading(text: str, hint: str | None) -> bool:
    stripped = text.strip()
    if _HEADING_HASH.match(stripped):
        return True
    if hint == "heading":
        return True
    if len(stripped) <= 48 and stripped.isupper() and any(c.isalpha() for c in stripped):
        return True
    return False


def _clean_heading(text: str) -> tuple[str, int]:
    match = _HEADING_HASH.match(text.strip())
    if match:
        return match.group(2).strip(), min(len(match.group(1)), 6)
    return text.strip().lstrip("#").strip(), 2


def build_note(
    raw: RawExtraction,
    source_image: str | None = None,
    low_confidence: float = 0.6,
) -> Note:
    """Assemble a Note, merging consecutive list items into single blocks."""
    blocks: list[Block] = []
    pending: list[RawItem] = []
    pending_type: BlockType | None = None

    def flush() -> None:
        nonlocal pending, pending_type
        if not pending or pending_type is None:
            pending, pending_type = [], None
            return
        confidences = [i.confidence for i in pending if i.confidence is not None]
        blocks.append(
            Block(
                type=pending_type,
                items=[_item_text(i, pending_type) for i in pending],
                origin=Block.model_fields["origin"].default,
                confidence=min(confidences) if confidences else None,
                source_image=source_image,
                flags=_flags_for(min(confidences) if confidences else None, "", low_confidence),
            )
        )
        pending, pending_type = [], None

    for item in raw.items:
        text = item.text.strip()
        if not text:
            continue

        bullet = _BULLET.match(text)
        numbered = _NUMBERED.match(text)
        list_type = (
            BlockType.BULLET_LIST if bullet
            else BlockType.NUMBERED_LIST if numbered
            else None
        )

        if list_type is not None:
            if pending_type is not None and pending_type != list_type:
                flush()
            pending_type = list_type
            pending.append(item)
            continue

        flush()

        if _looks_like_heading(text, item.hint):
            content, level = _clean_heading(text)
            blocks.append(_block(BlockType.HEADING, content, item, source_image,
                                 low_confidence, level=level))
        elif _is_math(text) or item.hint == "math":
            blocks.append(_block(BlockType.EQUATION, _strip_math_delims(text), item,
                                 source_image, low_confidence))
        else:
            blocks.append(_block(BlockType.TEXT, text, item, source_image, low_confidence))

    flush()

    title = raw.title_hint.strip().lstrip("#").strip() if raw.title_hint else None
    if not title:
        first_heading = next((b for b in blocks if b.type is BlockType.HEADING), None)
        title = first_heading.content if first_heading else None

    return Note(
        title=title,
        blocks=blocks,
        source_images=[source_image] if source_image else [],
    )


def _item_text(item: RawItem, block_type: BlockType) -> str:
    pattern = _BULLET if block_type is BlockType.BULLET_LIST else _NUMBERED
    match = pattern.match(item.text.strip())
    if not match:
        return item.text.strip()
    return match.group(match.lastindex).strip()


def _flags_for(confidence: float | None, content: str, threshold: float) -> list[Flag]:
    flags: list[Flag] = []
    if confidence is not None and confidence < threshold:
        flags.append(Flag.LOW_CONFIDENCE)
    return flags


def _block(
    block_type: BlockType,
    content: str,
    item: RawItem,
    source_image: str | None,
    threshold: float,
    level: int | None = None,
) -> Block:
    return Block(
        type=block_type,
        content=content,
        level=level,
        confidence=item.confidence,
        bbox=item.bbox,
        source_image=source_image,
        flags=_flags_for(item.confidence, content, threshold),
    )
