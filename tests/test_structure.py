"""Structuring is the stage that turns loose transcribed lines into typed
blocks. These tests pin the behaviours the VLM got wrong on real photos."""

from lectura.extract.base import RawExtraction, RawItem
from lectura.schema import BlockType, Flag, Origin
from lectura.structure import build_note


def note_from(*lines: str, **kw):
    items = [RawItem(text=t, **kw) for t in lines]
    return build_note(RawExtraction(items=items), source_image="x.jpg")


def test_latex_line_becomes_equation_not_text():
    # The VLM typed these as "text"; the whole point of this stage.
    note = note_from(r"$\frac{1}{\mu_i^2} = \beta_0 + \beta_1 x_{i,1}$")
    assert [b.type for b in note.blocks] == [BlockType.EQUATION]
    assert note.blocks[0].content.startswith(r"\frac")


def test_bare_arithmetic_is_an_equation():
    note = note_from("2x - y = 0")
    assert note.blocks[0].type is BlockType.EQUATION


def test_prose_mentioning_a_symbol_is_not_an_equation():
    note = note_from(
        "The gradient descent update rule adjusts weights using the learning rate"
    )
    assert note.blocks[0].type is BlockType.TEXT


def test_consecutive_bullets_merge_into_one_block():
    note = note_from("- Find Patterns", "- Predict Outcomes", "- Separate Signal")
    assert len(note.blocks) == 1
    assert note.blocks[0].type is BlockType.BULLET_LIST
    assert note.blocks[0].items == ["Find Patterns", "Predict Outcomes", "Separate Signal"]


def test_numbered_items_merge_and_keep_order():
    note = note_from("1. Build model", "2. Fit model", "3. Evaluate", "4. Improve")
    assert len(note.blocks) == 1
    assert note.blocks[0].type is BlockType.NUMBERED_LIST
    assert note.blocks[0].items[0] == "Build model"
    assert note.blocks[0].items[-1] == "Improve"


def test_switching_list_style_starts_a_new_block():
    note = note_from("- alpha", "- beta", "1. one", "2. two")
    assert [b.type for b in note.blocks] == [
        BlockType.BULLET_LIST,
        BlockType.NUMBERED_LIST,
    ]


def test_hash_and_shouting_headings():
    note = note_from("# STATISTICAL MODELING", "MODELING LOOP")
    assert all(b.type is BlockType.HEADING for b in note.blocks)
    assert note.blocks[0].content == "STATISTICAL MODELING"
    assert note.blocks[0].level == 1


def test_title_falls_back_to_first_heading():
    note = note_from("# Bayes' Theorem", "some prose here about it")
    assert note.title == "Bayes' Theorem"


def test_low_confidence_is_flagged_and_surfaces_for_review():
    note = note_from("something barely readable", confidence=0.4)
    block = note.blocks[0]
    assert Flag.LOW_CONFIDENCE in block.flags
    assert block.is_uncertain()
    assert note.needs_review() == [block]


def test_extraction_is_the_default_origin():
    note = note_from("plain line")
    assert note.blocks[0].origin is Origin.EXTRACTED
    assert note.supplements() == []


def test_labelled_equations_lose_their_delimiters():
    # Real pages label steps "a)", "b)" - the $ wrappers must still be stripped
    # or KaTeX renders them literally.
    note = note_from(r"a) $\sqrt{\mu_i} = \beta_0 + \beta_1 x_i$")
    block = note.blocks[0]
    assert block.type is BlockType.EQUATION
    assert "$" not in block.content
    assert block.content.startswith("a)")
    assert r"\sqrt{\mu_i}" in block.content


def test_inline_math_inside_prose_is_unwrapped_when_typed_as_equation():
    note = note_from(r"Solve for $\mu_i$")
    assert "$" not in note.blocks[0].content


def test_empty_extraction_is_not_silently_accepted():
    # A blank page presented as success is the worst outcome: the user waits
    # minutes and gets no reason and nothing to act on.
    note = build_note(RawExtraction(items=[]))
    assert note.blocks == []
    assert note.title is None
