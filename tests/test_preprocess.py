"""Preprocessing must improve real photos without mangling inputs that have
no page in them at all."""

import numpy as np
from PIL import Image

from lectura.preprocess import (
    Surface,
    classify_surface,
    find_page,
    flatten_illumination,
    preprocess,
    suppress_ruling,
    warp_to_page,
)


def _page_on_background(size=(400, 500), margin=60) -> Image.Image:
    """A bright rectangle on a mid-grey field, like paper on a desk."""
    array = np.full((size[1], size[0], 3), 110, dtype=np.uint8)
    array[margin:-margin, margin:-margin] = 245
    return Image.fromarray(array)


def test_light_page_and_dark_board_are_distinguished():
    assert classify_surface(_page_on_background()) is Surface.LIGHT_PAGE
    dark = Image.fromarray(np.full((300, 300, 3), 30, dtype=np.uint8))
    assert classify_surface(dark) is Surface.DARK_BOARD


def test_page_is_found_and_cropped_to_its_bounds():
    image = _page_on_background()
    corners = find_page(image)
    assert corners is not None
    warped = warp_to_page(image, corners)
    # The margin should be gone, so the result is smaller than the frame.
    assert warped.width < image.width
    assert warped.height < image.height


def test_no_page_reported_when_the_frame_is_uniform():
    # A tightly framed board has no page edge; inventing one would crop content.
    flat = Image.fromarray(np.full((400, 400, 3), 200, dtype=np.uint8))
    assert find_page(flat) is None


def test_illumination_flattening_reduces_a_lighting_gradient():
    gradient = np.tile(np.linspace(40, 240, 300, dtype=np.uint8), (300, 1))
    image = Image.fromarray(np.dstack([gradient] * 3))
    before = np.array(image.convert("L"), dtype=float)
    after = np.array(flatten_illumination(image).convert("L"), dtype=float)
    assert after.std() < before.std()


def test_ruling_suppression_lightens_faint_lines_but_keeps_dark_ink():
    array = np.full((200, 200, 3), 250, dtype=np.uint8)
    array[50, :] = 190   # faint printed rule
    array[100, :] = 25   # dark handwriting
    image = Image.fromarray(array)
    result = np.array(suppress_ruling(image).convert("L"), dtype=float)
    assert result[50].mean() > 190   # rule faded toward the page colour
    assert result[100].mean() < 60   # ink essentially untouched


def test_preprocess_reports_what_it_actually_did():
    result = preprocess(_page_on_background())
    assert result.page_found
    assert "dewarp" in result.steps
    assert "illumination" in result.steps
    assert result.surface is Surface.LIGHT_PAGE


def test_ruling_suppression_is_off_by_default():
    # Measured to cost formula accuracy: exact matches fell from 6 to 0.
    assert "ruling" not in preprocess(_page_on_background()).steps
    assert "ruling" in preprocess(_page_on_background(), ruling=True).steps


def test_contrast_boost_is_off_by_default():
    # CLAHE turned every handwritten mu into a capital M on a real page.
    # It stays opt-in until something measures it helping.
    assert "contrast" not in preprocess(_page_on_background()).steps
    assert "contrast" in preprocess(_page_on_background(), contrast=True).steps


def test_preprocess_steps_can_be_disabled():
    result = preprocess(_page_on_background(), dewarp=False, illumination=False)
    assert not result.page_found
    assert "dewarp" not in result.steps
    assert "illumination" not in result.steps


def test_default_chain_is_dewarp_and_illumination():
    # The configuration that measured best: everything else is opt-in.
    assert preprocess(_page_on_background()).steps == ["dewarp", "illumination"]
