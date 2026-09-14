"""The metric must not punish layout. A derivation merged into an aligned block
reads the same as the reference that writes it on one line."""

from lectura.evaluate.metrics import latex_exact_match, normalise_latex


def test_alignment_markup_is_layout_not_content():
    aligned = r"\begin{aligned} y &= 4 \cdot 0.5 \\ &= 2 \end{aligned}"
    assert latex_exact_match("y = 4 \\cdot 0.5 = 2", aligned)


def test_matrix_separators_still_count():
    # A transposed matrix is a real reading error.
    column = r"\begin{bmatrix} 1 \\ 2 \end{bmatrix}"
    row = r"\begin{bmatrix} 1 & 2 \end{bmatrix}"
    assert normalise_latex(column) != normalise_latex(row)
