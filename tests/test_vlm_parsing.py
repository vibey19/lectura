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
