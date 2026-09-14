"""The model can be cut off mid-answer. What it managed to read must survive."""

import json

from lectura.extract.vlm import _parse

WHOLE = json.dumps({
    "title": "Bayes",
    "lines": [
        {"text": "Conditional probability", "kind": "heading", "certain": True},
        {"text": "P(A|B)", "kind": "math", "certain": True},
    ],
})

# A real failure: the model looped on one token until it ran out of room,
# leaving an unterminated string and no closing braces.
TRUNCATED = (
    '{\n "title": "MULTI-LAYER PERCEPTRON",\n "lines": [\n'
    '  {"text": "INTRO", "kind": "heading", "certain": true},\n'
    '  {"text": "Neural networks are computational models", "kind": "body", "certain": true},\n'
    '  {"text": "\\\\bar{x} \\\\bar{x} \\\\bar{x} \\\\bar{x'
)


def test_complete_json_parses_without_salvage():
    parsed, salvaged = _parse(WHOLE)
    assert salvaged is False
    assert parsed["title"] == "Bayes"
    assert len(parsed["lines"]) == 2


def test_fenced_json_is_unwrapped():
    parsed, salvaged = _parse(f"```json\n{WHOLE}\n```")
    assert salvaged is False
    assert len(parsed["lines"]) == 2


def test_truncated_output_keeps_the_complete_lines():
    parsed, salvaged = _parse(TRUNCATED)
    assert salvaged is True
    assert parsed["title"] == "MULTI-LAYER PERCEPTRON"
    # The two finished lines survive; the unterminated one is dropped.
    assert [line["text"] for line in parsed["lines"]] == [
        "INTRO",
        "Neural networks are computational models",
    ]


def test_escapes_survive_salvage():
    raw = '{"lines": [{"text": "\\\\frac{1}{2} \\"x\\"", "kind": "math", "certain": false},'
    parsed, salvaged = _parse(raw)
    assert salvaged is True
    assert parsed["lines"][0]["text"] == '\\frac{1}{2} "x"'
    assert parsed["lines"][0]["certain"] is False


def test_unusable_output_yields_nothing_to_build_on():
    parsed, salvaged = _parse("total gibberish, no json here")
    assert salvaged is True
    assert parsed["lines"] == []


def test_salvage_collapses_a_repetition_loop():
    # A truncated response is usually truncated *because* the model looped, and
    # a loop emits complete objects: one real page salvaged into 128 blocks,
    # 120 of them the same expression.
    line = '{"text": "x = 1", "kind": "math", "certain": true},'
    raw = '{"title": "T", "lines": [' + line * 60 + '{"text": "unterminated'
    parsed, salvaged = _parse(raw)
    assert salvaged is True
    assert len(parsed["lines"]) <= 3
    assert parsed["lines"][0]["text"] == "x = 1"


def test_salvage_keeps_a_genuine_short_repeat():
    raw = (
        '{"lines": ['
        '{"text": "= 0", "kind": "math", "certain": true},'
        '{"text": "= 0", "kind": "math", "certain": true},'
        '{"text": "done", "kind": "body", "certain": true},'
    )
    parsed, _ = _parse(raw)
    assert [line["text"] for line in parsed["lines"]] == ["= 0", "= 0", "done"]


def _items(*texts):
    from lectura.extract.base import RawItem

    return [RawItem(text=t) for t in texts]


def test_a_whole_page_written_twice_is_kept_once():
    # GLM-OCR transcribed a page correctly, then wrote all of it out again.
    from lectura.extract.base import collapse_repeated_blocks

    page = ["TASK-1", "Given:", "$x = 1$", "$t = 1$"]
    assert [i.text for i in collapse_repeated_blocks(_items(*page, *page))] == page


def test_a_repeated_run_after_a_different_first_line_is_collapsed():
    from lectura.extract.base import collapse_repeated_blocks

    run = ["$= 0.25$", "$= x$", "$= 1$"]
    texts = [i.text for i in collapse_repeated_blocks(_items("head", *run, *run, "tail"))]
    assert texts == ["head", *run, "tail"]


def test_short_genuine_repeats_survive():
    # Notes legitimately repeat a line, or a pair such as "= 1" / "= 1".
    from lectura.extract.base import collapse_repeated_blocks

    texts = ["a", "= 1", "b", "= 1", "b", "c"]
    assert [i.text for i in collapse_repeated_blocks(_items(*texts))] == texts
