"""The Transformers path must read the model's answer exactly as the measured
Ollama path does. The model itself is injected, so no weights are needed."""

import pytest
from PIL import Image

from lectura.extract import ExtractionError
from lectura.extract.glm_transformers import GlmOcrTransformers
from lectura.pipeline import read_image


def test_answer_is_parsed_and_loops_collapsed_like_the_benchmarked_path():
    page = "TASK-1\nGiven:\n$$x = 1$$\n$$t = 1$$\n"
    extractor = GlmOcrTransformers(generate=lambda image: page + page)
    raw = extractor.extract(Image.new("RGB", (40, 40), "white"))
    assert [i.text for i in raw.items] == ["TASK-1", "Given:", "$x = 1$", "$t = 1$"]


def test_empty_answer_is_an_error_not_a_blank_note():
    with pytest.raises(ExtractionError):
        GlmOcrTransformers(generate=lambda image: "\n").extract(Image.new("RGB", (40, 40)))


def test_pipeline_returns_the_shape_the_web_app_expects():
    extractor = GlmOcrTransformers(generate=lambda image: "## Bayes\n$$P(A|B) = 1$$")
    result = read_image(Image.new("RGB", (300, 400), "white"), extractor,
                        use_preprocess=False, source_name="page.jpg")
    body = result.model_dump(mode="json")
    assert body["note"]["blocks"][0]["type"] == "heading"
    assert body["note"]["blocks"][1]["type"] == "equation"
    assert body["preview"].startswith("data:image/jpeg;base64,")
