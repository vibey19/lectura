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


def test_notation_fragments_are_not_accepted_as_titles():
    # One board produced "{- H2O" as its title: a piece of the page, not a name.
    for fragment in ("{- H2O", r"\frac{a}{b}", "$x$", "||", "]"):
        note = build_note(RawExtraction(items=[RawItem(text="body")],
                                        title_hint=fragment))
        assert note.title is None, fragment


def test_a_real_title_survives():
    note = build_note(RawExtraction(items=[RawItem(text="body")],
                                    title_hint="# Reactor classification"))
    assert note.title == "Reactor classification"


def test_notation_outside_a_short_allow_list_is_still_mathematics():
    # Without a type hint from the backend, these were typed as prose.
    for line in ("x_1 + x_2 + x_3", r"\lim_{n \to \infty} a_n", r"\Delta E \le 0"):
        assert note_from(line).blocks[0].type is BlockType.EQUATION, line


def test_identifiers_with_underscores_in_prose_stay_prose():
    assert note_from("the file_name variable is set here").blocks[0].type is BlockType.TEXT


def test_derivation_steps_join_the_equation_they_continue():
    # A real page: each step on its own line, read as one statement.
    note = note_from("y = w_2 h + b_2", r"= 4 \cdot 0.5 + 0", "= 2", hint="math")
    assert len(note.blocks) == 1
    content = note.blocks[0].content
    assert content.startswith(r"\begin{aligned}") and content.endswith(r"\end{aligned}")
    assert content.count("&=") == 3


def test_alignment_never_lands_inside_a_group():
    note = note_from(r"\sum_{i=1}^n x_i = 5", "= 6", hint="math")
    assert r"\sum_{i=1}^n x_i &= 5" in note.blocks[0].content


def test_an_implication_arrow_starts_a_new_statement():
    # Treating \Rightarrow as a continuation fused three derivations on a real
    # page into one block and cost an exact formula match.
    note = note_from(r"\sigma' = \sigma(1-\sigma)", r"\Rightarrow h' = 0.25", hint="math")
    assert len(note.blocks) == 2


def test_a_continuation_after_prose_is_not_merged_into_it():
    note = note_from("Pre-activation: compute the weighted sum", "= 0")
    assert [b.type for b in note.blocks] == [BlockType.TEXT, BlockType.EQUATION]


def test_a_merged_step_carries_its_doubt():
    items = [RawItem(text="y = 2", confidence=0.9), RawItem(text="= 3", confidence=0.4)]
    block = build_note(RawExtraction(items=items)).blocks[0]
    assert block.confidence == 0.4
    assert Flag.LOW_CONFIDENCE in block.flags


def test_formulas_in_capitals_are_not_headings():
    for line in ("$P(A|B) = 1$", "E = MC^2"):
        assert note_from(line).blocks[0].type is BlockType.EQUATION, line
    assert note_from("MODELING LOOP").blocks[0].type is BlockType.HEADING
