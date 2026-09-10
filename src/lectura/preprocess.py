"""Geometric and photometric correction before extraction.

Deliberately gentle. The consumer is a vision-language model, not a binariser,
and aggressive thresholding destroys the greyscale detail such models rely on.
The aim is to remove the things a camera added - perspective, page edges, uneven
lighting - while leaving the handwriting looking like handwriting.

Every step is optional and reports whether it fired, so a bad page can be
diagnosed from the result rather than guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import cv2
import numpy as np
from PIL import Image


class Surface(StrEnum):
    """Which kind of material the photo shows. Drives correction choices."""

    LIGHT_PAGE = "light_page"   # notebook, printed sheet, light slide
    DARK_BOARD = "dark_board"   # blackboard, dark-themed slide


@dataclass
class PreprocessResult:
    image: Image.Image
    surface: Surface
    steps: list[str] = field(default_factory=list)
    page_found: bool = False

    def summary(self) -> str:
        applied = ", ".join(self.steps) if self.steps else "none"
        return f"{self.surface.value} | {applied}"


def _to_cv(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def _to_pil(array: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(array, cv2.COLOR_BGR2RGB))


def classify_surface(image: Image.Image, dark_fraction: float = 0.45) -> Surface:
    """Dark board or light page, by how much of the frame is dark."""
    grey = cv2.cvtColor(_to_cv(image), cv2.COLOR_BGR2GRAY)
    dark = float((grey < 100).sum()) / grey.size
    return Surface.DARK_BOARD if dark >= dark_fraction else Surface.LIGHT_PAGE


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Order four points as top-left, top-right, bottom-right, bottom-left."""
    ordered = np.zeros((4, 2), dtype=np.float32)
    totals = points.sum(axis=1)
    ordered[0] = points[np.argmin(totals)]
    ordered[2] = points[np.argmax(totals)]
    diffs = np.diff(points, axis=1).ravel()
    ordered[1] = points[np.argmin(diffs)]
    ordered[3] = points[np.argmax(diffs)]
    return ordered


def _quad_from_mask(mask: np.ndarray) -> np.ndarray | None:
    """Largest blob in `mask` reduced to four corners, if it is quad-like."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    hull = cv2.convexHull(largest)

    # Relax the polygon tolerance until the hull collapses to four sides.
    peri = cv2.arcLength(hull, True)
    for tolerance in (0.02, 0.03, 0.04, 0.06, 0.08):
        approx = cv2.approxPolyDP(hull, tolerance * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2).astype(np.float32)

    # Not a clean quad (curved or occluded edge): fall back to the tightest
    # rotated rectangle, which still removes rotation and background.
    box = cv2.boxPoints(cv2.minAreaRect(largest))
    return np.asarray(box, dtype=np.float32)


def find_page(image: Image.Image, min_area_ratio: float = 0.25) -> np.ndarray | None:
    """Find the document's four corners, or None if no convincing page exists.

    Uses brightness segmentation rather than edge detection: the boundary between
    paper and a cloth or desk background is often too soft for Canny, which finds
    the handwriting instead of the page. Segmenting page-from-background and
    taking the largest region is far more reliable on real photos.

    Returning None matters - a photo framed tightly on a board has no page edge,
    and inventing one would crop away content.
    """
    cv_image = _to_cv(image)
    height, width = cv_image.shape[:2]
    scale = 900 / max(height, width)
    small = cv2.resize(cv_image, None, fx=scale, fy=scale) if scale < 1 else cv_image

    lightness = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)[:, :, 0]
    lightness = cv2.GaussianBlur(lightness, (7, 7), 0)

    # Dark boards invert the polarity: the subject is darker than its surround.
    dark_subject = classify_surface(image) is Surface.DARK_BOARD
    mode = cv2.THRESH_BINARY_INV if dark_subject else cv2.THRESH_BINARY
    _, mask = cv2.threshold(lightness, 0, 255, mode + cv2.THRESH_OTSU)

    # Close over handwriting so the page becomes one solid region.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    frame_area = small.shape[0] * small.shape[1]
    corners = _quad_from_mask(mask)
    if corners is None:
        return None

    area = cv2.contourArea(corners.astype(np.int32))
    # Too small to be the subject, or so large it is just the whole frame.
    if area < frame_area * min_area_ratio or area > frame_area * 0.985:
        return None

    corners = _order_corners(corners)
    if scale < 1:
        corners /= scale
    return corners


def warp_to_page(image: Image.Image, corners: np.ndarray) -> Image.Image:
    """Flatten the detected quadrilateral into an upright rectangle."""
    top_left, top_right, bottom_right, bottom_left = corners
    width = int(max(np.linalg.norm(top_right - top_left),
                    np.linalg.norm(bottom_right - bottom_left)))
    height = int(max(np.linalg.norm(bottom_left - top_left),
                     np.linalg.norm(bottom_right - top_right)))
    width, height = max(width, 32), max(height, 32)

    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(corners, destination)
    warped = cv2.warpPerspective(_to_cv(image), matrix, (width, height),
                                 flags=cv2.INTER_CUBIC)
    return _to_pil(warped)


def flatten_illumination(image: Image.Image, strength: float = 0.8) -> Image.Image:
    """Even out shadows and lighting gradients, preserving stroke texture.

    Divides by a heavily blurred copy - a standard background-division approach -
    on the L channel only, so colour-coded headings survive.
    """
    lab = cv2.cvtColor(_to_cv(image), cv2.COLOR_BGR2LAB)
    lightness = lab[:, :, 0].astype(np.float32)

    blur_radius = max(31, (min(image.size) // 12) | 1)   # must be odd
    background = cv2.GaussianBlur(lightness, (blur_radius, blur_radius), 0)
    background = np.maximum(background, 1.0)

    normalised = lightness / background * float(np.mean(background))
    blended = lightness * (1 - strength) + normalised * strength
    lab[:, :, 0] = np.clip(blended, 0, 255).astype(np.uint8)
    return _to_pil(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR))


def boost_contrast(image: Image.Image, clip_limit: float = 2.0) -> Image.Image:
    """Local contrast via CLAHE on lightness.

    Off by default, and it should stay off unless measured to help. On a page of
    handwritten statistics it silently turned every mu into a capital M - CLAHE
    amplifies local contrast tile by tile, which thickens and merges the thin
    descender that distinguishes the two. Extraction reported no doubt at all.

    An ablation over the correction chain isolated it: with contrast disabled the
    same page read mu correctly 12 times; with it enabled, zero times and M 12
    times. Illumination flattening and ruling suppression were both innocent.
    """
    lab = cv2.cvtColor(_to_cv(image), cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return _to_pil(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR))


def suppress_ruling(image: Image.Image, keep: float = 0.55) -> Image.Image:
    """Fade printed grid and ruled lines while leaving ink alone.

    Off by default. The idea is sound - ruling is lighter and less saturated
    than ink - but measured against reference transcriptions it consistently
    cost formula accuracy, in both configurations tested: formula error rose
    from 0.321 to 0.370 without illumination correction and from 0.224 to 0.273
    with it, and exact formula matches fell from 6 to 0.

    The likely cause is that a thin pen stroke antialiases to exactly the
    mid-tone, weakly coloured values this targets, so parts of the handwriting
    are lifted along with the grid.

    Measured on two pages only. Enough to justify not running it by default,
    not enough to call it settled.
    """
    lab = cv2.cvtColor(_to_cv(image), cv2.COLOR_BGR2LAB)
    lightness = lab[:, :, 0].astype(np.float32)
    chroma = np.hypot(lab[:, :, 1].astype(np.float32) - 128,
                      lab[:, :, 2].astype(np.float32) - 128)

    # Faint (light) and weakly coloured -> ruling. Dark or saturated -> ink.
    ruling = (lightness > 140) & (lightness < 232) & (chroma < 26)
    lifted = lightness.copy()
    lifted[ruling] = lightness[ruling] * keep + 255.0 * (1 - keep)
    lab[:, :, 0] = np.clip(lifted, 0, 255).astype(np.uint8)
    return _to_pil(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR))


def preprocess(
    image: Image.Image,
    *,
    dewarp: bool = True,
    illumination: bool = True,
    ruling: bool = False,
    contrast: bool = False,
) -> PreprocessResult:
    """Run the correction chain appropriate to the detected surface."""
    surface = classify_surface(image)
    steps: list[str] = []
    page_found = False

    if dewarp:
        corners = find_page(image)
        if corners is not None:
            image = warp_to_page(image, corners)
            steps.append("dewarp")
            page_found = True

    if illumination:
        image = flatten_illumination(image)
        steps.append("illumination")

    # Opt-in: measured to cost formula accuracy. See suppress_ruling.
    # Ruled paper is a light-page phenomenon; chalk boards have no printed grid.
    if ruling and surface is Surface.LIGHT_PAGE:
        image = suppress_ruling(image)
        steps.append("ruling")

    # Opt-in only: see boost_contrast for the failure it caused by default.
    if contrast:
        image = boost_contrast(image)
        steps.append("contrast")

    return PreprocessResult(
        image=image, surface=surface, steps=steps, page_found=page_found
    )
