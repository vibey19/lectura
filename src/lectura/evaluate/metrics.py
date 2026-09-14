"""Scoring for extraction quality.

Text and mathematics are scored separately and never averaged together. A page
of prose and a page of derivations fail in different ways, and the whole reason
this project exists is that classical OCR degrades with mathematical density
while leaving prose intact - a single blended number would hide exactly that.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _token_levenshtein(a: list[str], b: list[str]) -> int:
    """Edit distance over token sequences. Iterative two-row form."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ta in enumerate(a, start=1):
        current = [i]
        for j, tb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,               # deletion
                    current[j - 1] + 1,            # insertion
                    previous[j - 1] + (ta != tb),  # substitution
                )
            )
        previous = current
    return previous[-1]


def levenshtein(a: str, b: str) -> int:
    return _token_levenshtein(list(a), list(b))


def _normalise_text(text: str) -> str:
    """Fold away differences no reader would call an error."""
    text = unicodedata.normalize("NFKC", text)
    for fancy, plain in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'),
                         ("\u201d", '"'), ("\u2013", "-"), ("\u2014", "-")):
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip().lower()


def character_error_rate(reference: str, hypothesis: str) -> float:
    """CER = edit distance / reference length. 0 is perfect; above 1 is possible."""
    reference = _normalise_text(reference)
    hypothesis = _normalise_text(hypothesis)
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return levenshtein(reference, hypothesis) / len(reference)


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref_words = _normalise_text(reference).split()
    hyp_words = _normalise_text(hypothesis).split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return _token_levenshtein(ref_words, hyp_words) / len(ref_words)


# ---------------------------------------------------------------- LaTeX

_LATEX_SPACING = re.compile(
    r"\\(?:,|;|:|!|quad|qquad|thinspace|medspace|hspace\{[^}]*\})"
)
_LATEX_SIZING = re.compile(r"\\(?:left|right|big|Big|bigg|Bigg)\s*")
_LATEX_TOKEN = re.compile(r"\\[a-zA-Z]+|\\.|[a-zA-Z0-9]|[^\s]")
# Alignment environments only lay out a derivation: where the rows break and
# which relation they line up on. Matrices are deliberately not included - their
# & and \\ separate entries, and a transposed row is a real error.
_ALIGNMENT = re.compile(
    r"\\begin\{(aligned|align\*?|split|gathered)\}(.*?)\\end\{\1\}", re.DOTALL
)


def _unwrap_alignment(match: re.Match[str]) -> str:
    return re.sub(r"\\\\|&", " ", match.group(2))


def normalise_latex(latex: str) -> str:
    """Canonical form so cosmetic differences do not read as errors.

    ``\\frac{a}{b}`` and ``\\frac {a}{b}`` are the same expression. ``\\mu`` and
    ``M`` are not, and must stay distinguishable - that distinction is exactly
    what a preprocessing regression destroyed once already.
    """
    latex = latex.strip()
    if latex.startswith("$$") and latex.endswith("$$"):
        latex = latex[2:-2]
    latex = latex.strip("$").strip()
    if latex.startswith(r"\(") and latex.endswith(r"\)"):
        latex = latex[2:-2]
    if latex.startswith(r"\[") and latex.endswith(r"\]"):
        latex = latex[2:-2]
    latex = _ALIGNMENT.sub(_unwrap_alignment, latex)
    latex = _LATEX_SPACING.sub("", latex)
    latex = _LATEX_SIZING.sub("", latex)
    latex = re.sub(r"\s+", "", latex)
    latex = latex.replace(r"\cdot", "*").replace(r"\times", "*")
    latex = latex.replace(r"\mid", "|").replace(r"\vert", "|")
    return latex


def latex_tokens(latex: str) -> list[str]:
    """Split into LaTeX commands and single characters."""
    return _LATEX_TOKEN.findall(normalise_latex(latex))


def latex_exact_match(reference: str, hypothesis: str) -> bool:
    return normalise_latex(reference) == normalise_latex(hypothesis)


def latex_edit_distance(reference: str, hypothesis: str) -> float:
    """Normalised token-level edit distance between two expressions.

    Token level rather than character level: misreading ``\\beta`` is one
    mistake, not four.
    """
    ref, hyp = latex_tokens(reference), latex_tokens(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return min(1.0, _token_levenshtein(ref, hyp) / len(ref))


def latex_stream_distance(reference: list[str], hypothesis: list[str]) -> float:
    """Segmentation-independent formula score for a whole page.

    Positional matching punishes a model for splitting a derivation across lines
    differently from the reference, which is a formatting choice rather than a
    reading error. Concatenating every expression on each side and comparing the
    two token streams measures what we actually care about - whether the
    mathematics on the page was read correctly - and is unaffected by where the
    line breaks fall.
    """
    ref = [t for f in reference for t in latex_tokens(f)]
    hyp = [t for f in hypothesis for t in latex_tokens(f)]
    if not ref:
        return 0.0 if not hyp else 1.0
    return min(1.0, _token_levenshtein(ref, hyp) / len(ref))


@dataclass
class PageScore:
    """Scores for one page. Text and formulas stay separate on purpose."""

    page_id: str
    cer: float
    wer: float
    formula_count: int = 0
    formula_exact: int = 0          # strict, positional
    formula_edit_distance: float = 0.0   # strict, positional
    formula_stream_distance: float = 0.0  # segmentation-independent; primary

    @property
    def formula_exact_rate(self) -> float:
        return self.formula_exact / self.formula_count if self.formula_count else 0.0
