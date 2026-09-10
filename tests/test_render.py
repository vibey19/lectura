from lectura.render import available_themes, render
from lectura.schema import Block, BlockType, Note, Origin


def test_all_four_themes_render_the_same_note():
    note = Note(title="T", blocks=[Block(type=BlockType.TEXT, content="hello")])
    themes = available_themes()
    assert len(themes) == 4
    for theme in themes:
        assert "hello" in render(note, theme)


def test_supplements_are_visually_marked():
    note = Note(blocks=[Block(type=BlockType.TEXT, content="added",
                              origin=Origin.SUPPLEMENT)])
    assert "supplement" in render(note)


def test_equations_are_handed_to_katex_unescaped_as_source():
    note = Note(blocks=[Block(type=BlockType.EQUATION, content=r"\frac{a}{b}")])
    html = render(note)
    assert "katex-src" in html
    assert r"\frac{a}{b}" in html


def test_html_special_characters_are_escaped():
    note = Note(blocks=[Block(type=BlockType.TEXT, content="<script>x</script>")])
    assert "<script>x</script>" not in render(note)


def test_inline_math_in_prose_reaches_katex():
    note = Note(blocks=[Block(type=BlockType.TEXT, content=r"Solve for $\mu_i$ now")])
    html = render(note)
    assert "katex-inline" in html
    assert "$" not in html.split("<main")[1].split("</main>")[0]


def test_inline_math_in_list_items_reaches_katex():
    note = Note(blocks=[Block(type=BlockType.BULLET_LIST,
                              items=[r"take $\sqrt{x}$", "plain item"])])
    assert "katex-inline" in render(note)


def test_escaping_still_applies_around_inline_math():
    note = Note(blocks=[Block(type=BlockType.TEXT, content="<b>a</b> $x$")])
    out = render(note)
    assert "<b>a</b>" not in out
    assert "katex-inline" in out
