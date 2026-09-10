"""Load a source image into a normalised RGB form.

iPhone photos arrive as HEIC with EXIF rotation, so both need handling before
anything downstream sees pixels.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

HEIC_SUFFIXES = {".heic", ".heif"}
SUPPORTED = HEIC_SUFFIXES | {".jpg", ".jpeg", ".png", ".webp"}


class UnsupportedImage(ValueError):
    pass


def _decode_heic(path: Path) -> Image.Image:
    """Decode HEIC via macOS `sips`, falling back to pillow-heif if present."""
    try:
        import pillow_heif  # type: ignore

        pillow_heif.register_heif_opener()
        return Image.open(path)
    except ImportError:
        pass

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "converted.jpg"
        result = subprocess.run(
            ["sips", "-s", "format", "jpeg", str(path), "--out", str(out)],
            capture_output=True,
        )
        if result.returncode != 0 or not out.exists():
            raise UnsupportedImage(
                f"cannot decode HEIC {path.name}; install pillow-heif"
            )
        return Image.open(out).copy()


def load(path: str | Path) -> Image.Image:
    """Return an upright RGB image."""
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED:
        raise UnsupportedImage(f"{path.suffix} not supported")

    img = _decode_heic(path) if path.suffix.lower() in HEIC_SUFFIXES else Image.open(path)
    img = ImageOps.exif_transpose(img)   # honour camera rotation
    return img.convert("RGB")


def fit_within(img: Image.Image, longest_edge: int) -> Image.Image:
    """Downscale so the longest edge is at most `longest_edge`. Never upscales.

    Inference cost scales with pixel count, so this is the main latency lever.
    """
    if max(img.size) <= longest_edge:
        return img
    img = img.copy()
    img.thumbnail((longest_edge, longest_edge), Image.LANCZOS)
    return img
