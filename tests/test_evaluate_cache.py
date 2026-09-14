"""A model pass over the labelled set takes minutes; structuring and scoring
take milliseconds. The cache is what makes structuring changes measurable."""

from PIL import Image

from lectura.evaluate.dataset import Reference
from lectura.evaluate.runner import evaluate
from lectura.extract.base import ExtractionError, RawExtraction, RawItem


class Counting:
    name = "counting"

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def extract(self, image):
        self.calls += 1
        if self.fail:
            raise ExtractionError("nothing readable")
        return RawExtraction(items=[RawItem(text="$x = 1$", hint="math")], seconds=3.0)


def _reference(tmp_path) -> Reference:
    image = tmp_path / "page.png"
    Image.new("RGB", (80, 60), "white").save(image)
    return Reference(page_id="p1", source=str(image), surface="notebook",
                     formulas=["x = 1"])


def test_second_run_is_scored_from_the_cache_without_the_model(tmp_path):
    reference, cache = _reference(tmp_path), tmp_path / "cache"
    first = Counting()
    report = evaluate(first, [reference], use_preprocess=False, cache=cache)
    assert first.calls == 1 and report.scores[0].formula_exact == 1

    second = Counting()
    again = evaluate(second, [reference], use_preprocess=False, cache=cache)
    assert second.calls == 0
    assert again.scores[0].formula_exact == 1
    assert again.seconds == 3.0   # original latency is preserved, not re-timed


def test_a_cached_failure_is_still_scored_as_a_failure(tmp_path):
    reference, cache = _reference(tmp_path), tmp_path / "cache"
    evaluate(Counting(fail=True), [reference], use_preprocess=False, cache=cache)
    report = evaluate(Counting(), [reference], use_preprocess=False, cache=cache)
    assert report.failures == ["p1"]
    assert report.scores[0].formula_stream_distance == 1.0


def test_cached_only_never_calls_the_model(tmp_path):
    reference = _reference(tmp_path)
    extractor = Counting()
    report = evaluate(extractor, [reference], use_preprocess=False,
                      cache=tmp_path / "empty", cached_only=True)
    assert extractor.calls == 0 and report.scores == []
