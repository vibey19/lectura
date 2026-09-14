"""Split Markdown-with-LaTeX transcriptions into raw items.

Document OCR models - Pix2Text, GLM-OCR - answer in Markdown with display
mathematics in `$$...$$` or `\\[...\\]` rather than in a structured format. Both
are read the same way: display blocks become maths items, every other non-empty
line becomes prose, and reading order is preserved. Headings and list markers
are left in the text for `structure.py` to interpret, as for any backend.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from lectura.extract.base import RawItem

_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", re.DOTALL)


def markdown_items(text: str) -> Iterator[RawItem]:
    position = 0
    for match in _DISPLAY_MATH.finditer(text):
        yield from _prose(text[position : match.start()])
        expression = next(g for g in match.groups() if g is not None).strip()
        if expression:
            yield RawItem(text=f"${expression}$", hint="math")
        position = match.end()
    yield from _prose(text[position:])


def _prose(chunk: str) -> Iterator[RawItem]:
    for line in chunk.splitlines():
        line = line.strip()
        if line and not line.startswith("```"):
            yield RawItem(text=line, hint="body")
