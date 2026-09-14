"""Document OCR models answer in Markdown with LaTeX. What they read must reach
structuring in order, with display maths kept apart from prose."""

import pytest
from PIL import Image

from lectura.extract import ExtractionError, OllamaVLM
from lectura.extract.markdown import markdown_items


def test_display_maths_and_prose_keep_reading_order():
    text = "## Problem 3\n\nSquare both sides\n$$\\mu_i = (\\beta_0)^2$$\nthen\n\\[ x = 1 \\]"
    items = [(i.hint, i.text) for i in markdown_items(text)]
    assert items == [
        ("body", "## Problem 3"),
        ("body", "Square both sides"),
        ("math", "$\\mu_i = (\\beta_0)^2$"),
        ("body", "then"),
        ("math", "$x = 1$"),
    ]


def test_multi_line_display_blocks_stay_one_expression():
    items = list(markdown_items("$$\na = b\n+ c\n$$"))
    assert len(items) == 1 and items[0].hint == "math"


def test_code_fences_are_not_transcribed_as_text():
    assert [i.text for i in markdown_items("```markdown\nhello\n```")] == ["hello"]


def _vlm_answering(monkeypatch, response: str, **kwargs) -> tuple[OllamaVLM, dict]:
    sent: dict = {}
    vlm = OllamaVLM(model="glm-ocr", output="markdown", **kwargs)

    def fake_post(payload):
        sent.update(payload)
        return {"response": response, "done_reason": "stop"}

    monkeypatch.setattr(vlm, "_post", fake_post)
    return vlm, sent


def test_markdown_mode_sends_a_task_prompt_and_no_json_format(monkeypatch):
    vlm, sent = _vlm_answering(monkeypatch, "Title\n$$E = mc^2$$")
    raw = vlm.extract(Image.new("RGB", (40, 40), "white"))
    assert sent["prompt"] == "Text Recognition:"
    assert "format" not in sent
    assert [i.hint for i in raw.items] == ["body", "math"]


def test_markdown_mode_still_refuses_an_empty_answer(monkeypatch):
    vlm, _ = _vlm_answering(monkeypatch, "  \n ")
    with pytest.raises(ExtractionError):
        vlm.extract(Image.new("RGB", (40, 40), "white"))


def test_changing_anything_the_model_sees_changes_the_cache_signature():
    base = OllamaVLM(model="m")
    assert OllamaVLM(model="m", prompt="other").signature != base.signature
    assert OllamaVLM(model="m", think=False).signature != base.signature
    assert OllamaVLM(model="m", output="markdown").signature != base.signature
    assert OllamaVLM(model="m").signature == base.signature
