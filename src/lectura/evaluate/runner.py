"""Run an extractor over the labelled set and score it."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from lectura import ingest
from lectura.evaluate.dataset import Reference, load_all
from lectura.evaluate.metrics import (
    PageScore,
    character_error_rate,
    latex_edit_distance,
    latex_exact_match,
    latex_stream_distance,
    word_error_rate,
)
from lectura.extract.base import ExtractionError, Extractor, RawExtraction
from lectura.preprocess import preprocess
from lectura.schema import BlockType, Note
from lectura.structure import build_note


@dataclass
class Report:
    backend: str
    scores: list[PageScore]
    seconds: float
    failures: list[str] = field(default_factory=list)
    """Pages the extractor could not read at all.

    Scored as total failures rather than skipped: a backend that returns nothing
    on a page has not earned a better average by omitting it.
    """

    def mean(self, attribute: str) -> float:
        values = [getattr(s, attribute) for s in self.scores]
        return statistics.mean(values) if values else 0.0

    def summary(self) -> str:
        formulas = sum(s.formula_count for s in self.scores)
        exact = sum(s.formula_exact for s in self.scores)
        failed = f" failed={len(self.failures)}" if self.failures else ""
        return (
            f"{self.backend}: pages={len(self.scores)} "
            f"CER={self.mean('cer'):.3f} WER={self.mean('wer'):.3f} "
            f"formula_exact={exact}/{formulas} "
            f"formula_stream={self.mean('formula_stream_distance'):.3f} "
            f"{self.seconds:.0f}s{failed}"
        )


def note_text(note: Note) -> str:
    """Prose from a note, excluding equations, in reading order."""
    parts: list[str] = []
    for block in note.blocks:
        if block.type is BlockType.EQUATION:
            continue
        parts.append(block.content)
        parts.extend(block.items)
    return " ".join(p for p in parts if p)


def note_formulas(note: Note) -> list[str]:
    return [b.content for b in note.blocks if b.type is BlockType.EQUATION]


def score_page(reference: Reference, note: Note) -> PageScore:
    """Score one page.

    Formulas are matched positionally in reading order. That is strict - one
    missed equation shifts everything after it - so a missing formula is
    penalised as the real failure it is rather than being quietly skipped.
    """
    predicted = note_formulas(note)
    exact = 0
    distances: list[float] = []
    for index, expected in enumerate(reference.formulas):
        candidate = predicted[index] if index < len(predicted) else ""
        if latex_exact_match(expected, candidate):
            exact += 1
        distances.append(latex_edit_distance(expected, candidate))

    return PageScore(
        page_id=reference.page_id,
        formula_stream_distance=latex_stream_distance(reference.formulas, predicted),
        cer=character_error_rate(reference.text, note_text(note)),
        wer=word_error_rate(reference.text, note_text(note)),
        formula_count=len(reference.formulas),
        formula_exact=exact,
        formula_edit_distance=statistics.mean(distances) if distances else 0.0,
    )


def _read_cached(path: Path | None) -> RawExtraction | None | Literal["failed"]:
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get("failed"):
        return "failed"
    return RawExtraction.from_dict(data)


def _write_cached(path: Path | None, raw: RawExtraction | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"failed": True} if raw is None else raw.to_dict()
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False))


def evaluate(
    extractor: Extractor,
    references: list[Reference] | None = None,
    *,
    max_edge: int = 2200,
    use_preprocess: bool = True,
    root: Path = Path("data/eval"),
    cache: Path | None = None,
) -> Report:
    """Score `extractor` over the labelled set.

    With `cache`, each page's raw extraction is stored on first read and reused
    afterwards. A model pass over the set takes around ten minutes while
    structuring and scoring take milliseconds, so caching is what makes changes
    to `structure.py` measurable at all. The cache is keyed by page only; the
    caller is responsible for giving each backend configuration its own
    directory.
    """
    references = references if references is not None else load_all(root)
    scores: list[PageScore] = []
    failures: list[str] = []
    total = 0.0

    for reference in references:
        path = Path(reference.source)
        cached_path = cache / f"{reference.page_id}.json" if cache else None
        cached = _read_cached(cached_path)

        if cached is None:
            if not path.exists():
                continue
            image = ingest.load(path)
            if use_preprocess:
                image = preprocess(image).image
            image = ingest.fit_within(image, max_edge)
            try:
                cached = extractor.extract(image)
            except ExtractionError:
                cached = "failed"
            _write_cached(cached_path, None if cached == "failed" else cached)

        raw = cached
        if raw == "failed":
            # Reading nothing is a result, not a reason to abandon the run.
            failures.append(reference.page_id)
            scores.append(
                PageScore(
                    page_id=reference.page_id,
                    cer=1.0,
                    wer=1.0,
                    formula_count=len(reference.formulas),
                    formula_exact=0,
                    formula_edit_distance=1.0,
                    formula_stream_distance=1.0,
                )
            )
            continue

        total += raw.seconds
        scores.append(score_page(reference, build_note(raw, source_image=path.name)))

    return Report(
        backend=getattr(extractor, "signature", extractor.name),
        scores=scores, seconds=total, failures=failures,
    )
