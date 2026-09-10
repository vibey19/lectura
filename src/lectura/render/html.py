"""Render a Note to standalone HTML.

Themes are pure presentation: the same Note renders under any theme without
re-running extraction. Maths is rendered client-side by KaTeX.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from lectura.schema import Block, BlockType, Note, Origin

THEMES_DIR = Path(__file__).parent / "themes"
_INLINE_MATH = re.compile(r"\$(.+?)\$|\\\((.+?)\\\)", re.DOTALL)
KATEX = "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist"


def available_themes() -> list[str]:
    return sorted(p.stem for p in THEMES_DIR.glob("*.css"))


def _theme_css(theme: str) -> str:
    path = THEMES_DIR / f"{theme}.css"
    if not path.exists():
        raise ValueError(
            f"unknown theme {theme!r}; available: {', '.join(available_themes())}"
        )
    return path.read_text()


def _inline(text: str) -> str:
    """Escape text, then hand any inline $...$ spans to KaTeX.

    Transcribed prose routinely carries inline notation ("Solve for $\\mu_i$"),
    which would otherwise render as literal dollar signs.
    """
    escaped = html.escape(text)

    def wrap(match: re.Match[str]) -> str:
        expr = next(g for g in match.groups() if g is not None)
        return f'<span class="katex-inline">{expr}</span>'

    return _INLINE_MATH.sub(wrap, escaped)


def _render_block(block: Block) -> str:
    classes = ["block", f"block-{block.type.value}"]
    if block.origin is Origin.SUPPLEMENT:
        classes.append("supplement")
    if block.is_uncertain():
        classes.append("uncertain")

    attrs = f' class="{" ".join(classes)}" data-block-id="{block.id}"'
    if block.confidence is not None:
        attrs += f' data-confidence="{block.confidence:.2f}"'

    flag_markup = ""
    if block.flags:
        names = ", ".join(f.value.replace("_", " ") for f in block.flags)
        flag_markup = f'<span class="flag" title="{html.escape(names)}">!</span>'

    if block.type is BlockType.HEADING:
        level = block.level or 2
        return f"<h{level}{attrs}>{html.escape(block.content)}{flag_markup}</h{level}>"

    if block.type is BlockType.EQUATION:
        return (
            f"<div{attrs}>{flag_markup}"
            f'<span class="katex-src">{html.escape(block.content)}</span></div>'
        )

    if block.type in (BlockType.BULLET_LIST, BlockType.NUMBERED_LIST):
        tag = "ul" if block.type is BlockType.BULLET_LIST else "ol"
        items = "".join(f"<li>{_inline(i)}</li>" for i in block.items)
        return f"<{tag}{attrs}>{items}</{tag}>"

    if block.type is BlockType.CODE:
        return f"<pre{attrs}><code>{html.escape(block.content)}</code></pre>"

    return f"<p{attrs}>{flag_markup}{_inline(block.content)}</p>"


def render(note: Note, theme: str = "academic") -> str:
    body = "\n".join(_render_block(b) for b in note.blocks)
    title = html.escape(note.title or "Untitled notes")
    uncertain = len(note.needs_review())
    banner = (
        f'<div class="review-banner">{uncertain} block(s) flagged for review</div>'
        if uncertain
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{KATEX}/katex.min.css">
<style>{_theme_css(theme)}</style>
</head>
<body>
<main class="note" data-theme="{html.escape(theme)}">
<h1 class="note-title">{title}</h1>
{banner}
{body}
</main>
<script src="{KATEX}/katex.min.js"></script>
<script>
function typeset(selector, displayMode) {{
  document.querySelectorAll(selector).forEach(function (el) {{
    try {{
      katex.render(el.textContent, el, {{displayMode: displayMode, throwOnError: false}});
    }} catch (err) {{
      el.classList.add('katex-failed');
    }}
  }});
}}
typeset('.katex-src', true);
typeset('.katex-inline', false);
</script>
</body>
</html>"""


def write(note: Note, path: str | Path, theme: str = "academic") -> Path:
    path = Path(path)
    path.write_text(render(note, theme))
    return path


def write_json(note: Note, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(note.model_dump(mode="json"), indent=2))
    return path
