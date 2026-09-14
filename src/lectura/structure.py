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
# Any LaTeX command except the few that wrap prose. An allow-list of a dozen
# names missed \lim, \infty, \Delta, \le and most of the rest of mathematics.
_MATH_CMD = re.compile(r"\\(?!(?:text|textbf|textit|emph|mathrm)\b)[a-zA-Z]+")
# Subscripts and superscripts: x_1, x_{i,1}, e^{-x}, \mu_i^2.
_SCRIPT = re.compile(r"[A-Za-z0-9)}\]][_^][{A-Za-z0-9(\\-]")
# A derivation step: the line continues the expression above it. Implication
# arrows are not steps - on real pages "\Rightarrow" opens the next statement,
# and treating it as a continuation fused three derivations into one.
_CONTINUATION = re.compile(r"^\s*(=|\\approx)")
_ALIGNED = re.compile(r"^\\begin\{aligned\}(.*)\\end\{aligned\}$", re.DOTALL)
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
    prose = re.findall(r"[A-Za-z]{4,}", _MATH_CMD.sub("", _MATH_DELIM.sub(" ", stripped)))
    if _MATH_CMD.search(stripped):
        # Prose mentioning one symbol is not an equation; notation-dense is.
        return len(prose) <= 3
    if _SCRIPT.search(stripped):
        # Stricter than commands: identifiers such as file_name also match.
        return len(prose) <= 1
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
            content = _strip_math_delims(text)
            previous = blocks[-1] if blocks else None
            if (
                previous is not None
                and previous.type is BlockType.EQUATION
                and _CONTINUATION.match(content)
            ):
                blocks[-1] = _continue_equation(previous, content, item, low_confidence)
            else:
                blocks.append(_block(BlockType.EQUATION, content, item,
                                     source_image, low_confidence))
        else:
            blocks.append(_block(BlockType.TEXT, text, item, source_image, low_confidence))

    flush()

    title = _clean_title(raw.title_hint)
    if not title:
        first_heading = next((b for b in blocks if b.type is BlockType.HEADING), None)
        title = _clean_title(first_heading.content) if first_heading else None

    return Note(
        title=title,
        blocks=blocks,
        source_images=[source_image] if source_image else [],
    )


def _clean_title(candidate: str | None) -> str | None:
    """Reject titles that are really fragments of notation.

    The model's title guess is sometimes a piece of the page rather than a name
    for it - one board produced "{- H2O". A title needs a couple of words of
    actual prose to be worth showing.
    """
    if not candidate:
        return None
    title = candidate.strip().lstrip("#").strip()
    if not title or title[0] in "{}\\$[]|":
        return None
    letters = sum(character.isalpha() for character in title)
    if letters < 3 or letters < len(title) / 3:
        return None
    return title


def _first_top_level_equals(latex: str) -> int:
    """Index of the first '=' outside braces, or -1.

    An alignment marker inside a group - the '=' of \\sum_{i=1} - does not
    parse, so only the relation at the top level can carry it.
    """
    depth = 0
    for index, character in enumerate(latex):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == "=" and depth == 0:
            return index
    return -1


def _continue_equation(
    previous: Block, continuation: str, item: RawItem, threshold: float
) -> Block:
    """Fold a derivation step into the equation it continues.

    Handwritten working puts each step on its own line - "y = w x + b",
    "= 4 * 0.5 + 0", "= 2" - and a reader parses the column as one statement.
    Kept as separate blocks, the steps read as three unrelated equations, two of
    which start with a dangling '='. They are joined into one aligned
    derivation, so the steps still line up on their relation.
    """
    match = _ALIGNED.match(previous.content)
    if match:
        rows = match.group(1).strip()
    else:
        head = previous.content
        split = _first_top_level_equals(head)
        rows = f"{head[:split]}&{head[split:]}" if split >= 0 else f"&{head}"

    content = f"\\begin{{aligned}} {rows} \\\\ &{continuation.strip()} \\end{{aligned}}"

    confidences = [c for c in (previous.confidence, item.confidence) if c is not None]
    confidence = min(confidences) if confidences else None
    return previous.model_copy(update={
        "content": content,
        "confidence": confidence,
        "flags": _flags_for(confidence, content, threshold),
    })


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
