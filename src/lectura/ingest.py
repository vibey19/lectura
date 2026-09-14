"""Load a source image into a normalised RGB form.

iPhone photos arrive as HEIC with EXIF rotation, so both need handling before
anything downstream sees pixels.

HEIC is decoded by pillow-heif, registered as a Pillow opener at import. An
earlier version shelled out to macOS `sips`, which worked on the machine it was
written on and nowhere else: the Linux container rejected every iPhone photo.
"""

from __future__ import annotations

import io
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

HEIC_SUFFIXES = {".heic", ".heif"}
SUPPORTED = HEIC_SUFFIXES | {".jpg", ".jpeg", ".png", ".webp"}


class UnsupportedImage(ValueError):
    pass


def _normalise(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)   # honour camera rotation
    return img.convert("RGB")


def load(path: str | Path) -> Image.Image:
    """Return an upright RGB image."""
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED:
        raise UnsupportedImage(f"{path.suffix} not supported")
    return _normalise(Image.open(path))


def decode(payload: bytes) -> Image.Image:
    """Decode an in-memory upload, HEIC included, to an upright RGB image.

    The format is sniffed from the bytes, not the filename: a browser may send a
    HEIC photo named `.jpg`, or no useful name at all.
    """
    return _normalise(Image.open(io.BytesIO(payload)))


def fit_within(img: Image.Image, longest_edge: int) -> Image.Image:
    """Downscale so the longest edge is at most `longest_edge`. Never upscales.

    Inference cost scales with pixel count, so this is the main latency lever.
    """
    if max(img.size) <= longest_edge:
        return img
    img = img.copy()
    img.thumbnail((longest_edge, longest_edge), Image.LANCZOS)
    return img
