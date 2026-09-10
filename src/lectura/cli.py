"""Command line entry point: image in, structured note plus rendered HTML out."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lectura import ingest
from lectura.extract import OllamaVLM, Tesseract
from lectura.preprocess import preprocess
from lectura.render import available_themes, write, write_json
from lectura.schema import Note
from lectura.structure import build_note


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lectura", description="Turn a lecture image into structured notes."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="source photo, or an existing note .json to re-render",
    )
    parser.add_argument("-o", "--out", type=Path, default=Path("out"),
                        help="output directory (default: ./out)")
    parser.add_argument("-t", "--theme", default="academic",
                        choices=available_themes())
    parser.add_argument("-b", "--backend", default="vlm", choices=["vlm", "tesseract"])
    parser.add_argument("-m", "--model", default="qwen2.5vl:7b")
    parser.add_argument("--max-edge", type=int, default=2200,
                        help="downscale longest edge; drives latency (default: 2200)")
    parser.add_argument("--no-preprocess", action="store_true",
                        help="skip page detection, dewarp and lighting correction")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.source.exists():
        print(f"no such file: {args.source}", file=sys.stderr)
        return 1

    # Re-rendering an existing note must never re-run extraction: themes are a
    # presentation layer over the stored structure.
    if args.source.suffix.lower() == ".json":
        note = Note.model_validate_json(args.source.read_text())
        args.out.mkdir(parents=True, exist_ok=True)
        path = write(note, args.out / f"{args.source.stem}.{args.theme}.html",
                     theme=args.theme)
        print(f"rendered {len(note.blocks)} blocks -> {path}")
        return 0

    image = ingest.load(args.source)
    if not args.no_preprocess:
        result = preprocess(image)
        image = result.image
        print(f"preprocess: {result.summary()}")
    image = ingest.fit_within(image, args.max_edge)

    extractor = (
        Tesseract() if args.backend == "tesseract" else OllamaVLM(model=args.model)
    )

    print(f"extracting with {extractor.name} at {image.width}x{image.height} ...")
    try:
        raw = extractor.extract(image)
    except RuntimeError as exc:
        print(f"extraction failed: {exc}", file=sys.stderr)
        return 2

    note = build_note(raw, source_image=args.source.name)

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.source.stem
    json_path = write_json(note, args.out / f"{stem}.json")
    html_path = write(note, args.out / f"{stem}.{args.theme}.html", theme=args.theme)

    flagged = note.needs_review()
    print(
        f"{len(note.blocks)} blocks in {raw.seconds}s "
        f"({len(flagged)} flagged for review)"
    )
    print(f"  {json_path}\n  {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
