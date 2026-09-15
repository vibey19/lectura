"""Publish the demo Space: the Gradio app plus the lectura package it imports.

    python space/deploy.py                  # to Jainil19/lectura
    python space/deploy.py --space user/name

The package is uploaded from this checkout rather than installed from GitHub,
so the Space always runs exactly the code in the working tree - including
changes not yet pushed - and never a moving branch.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import tomllib
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
SPACE_DIR = ROOT / "space"
PACKAGE = ROOT / "src" / "lectura"


def requirements() -> str:
    """The package's own dependencies plus the model stack, one per line."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    extras = project["optional-dependencies"]["glm"]
    skip = ("fastapi", "uvicorn", "python-multipart")   # the Space serves through Gradio
    deps = [d for d in project["dependencies"] if not d.startswith(skip)]
    return "\n".join([*deps, *extras, "spaces"]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--space", default="Jainil19/lectura")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as staging:
        stage = Path(staging)
        for name in ("app.py", "README.md"):
            shutil.copy(SPACE_DIR / name, stage / name)
        (stage / "requirements.txt").write_text(requirements())
        shutil.copytree(
            PACKAGE, stage / "lectura",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "static"),
        )
        HfApi().upload_folder(
            repo_id=args.space, repo_type="space", folder_path=stage,
            commit_message="Deploy from lectura checkout",
            delete_patterns=["lectura/**"],
        )
    print(f"deployed https://huggingface.co/spaces/{args.space}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
