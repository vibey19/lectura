"""Run an extractor over the labelled set and score it."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path

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
from lectura.extract.base import Extractor
from lectura.preprocess import preprocess
from lectura.schema import BlockType, Note
from lectura.structure import build_note


@dataclass
class Report:
    backend: str
    scores: list[PageScore]
    seconds: float

    def mean(self, attribute: str) -> float:
        values = [getattr(s, attribute) for s in self.scores]
        return statistics.mean(values) if values else 0.0

    def summary(self) -> str:
        formulas = sum(s.formula_count for s in self.scores)
        exact = sum(s.formula_exact for s in self.scores)
        return (
            f"{self.backend}: pages={len(self.scores)} "
            f"CER={self.mean('cer'):.3f} WER={self.mean('wer'):.3f} "
            f"formula_exact={exact}/{formulas} "
            f"formula_stream={self.mean('formula_stream_distance'):.3f} "
            f"{self.seconds:.0f}s"
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


def evaluate(
    extractor: Extractor,
    references: list[Reference] | None = None,
    *,
    max_edge: int = 2200,
    use_preprocess: bool = True,
    root: Path = Path("data/eval"),
) -> Report:
    references = references if references is not None else load_all(root)
    scores: list[PageScore] = []
    total = 0.0

    for reference in references:
        path = Path(reference.source)
        if not path.exists():
            continue
        image = ingest.load(path)
        if use_preprocess:
            image = preprocess(image).image
        image = ingest.fit_within(image, max_edge)

        raw = extractor.extract(image)
        total += raw.seconds
        scores.append(score_page(reference, build_note(raw, source_image=path.name)))

    return Report(backend=extractor.name, scores=scores, seconds=total)
