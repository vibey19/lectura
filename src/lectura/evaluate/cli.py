"""`lectura-eval`: score a backend against the labelled set.

    lectura-eval                          # VLM, default pipeline
    lectura-eval -b tesseract --no-preprocess
    lectura-eval --refresh                # ignore cached extractions

Raw extractions are cached under `results/raw/`, one directory per backend
configuration, so re-scoring after a change to structuring or metrics costs
milliseconds instead of a model pass.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from lectura.evaluate.dataset import DEFAULT_ROOT, load_all, missing_images
from lectura.evaluate.runner import evaluate


def _extractor(backend: str, model: str, no_think: bool, output: str, prompt: str):
    from lectura.extract import OllamaVLM, Pix2TextOCR, Tesseract

    if backend == "tesseract":
        return Tesseract()
    if backend == "pix2text":
        return Pix2TextOCR()
    from lectura.extract.vlm import PROMPTS

    return OllamaVLM(
        model=model,
        think=False if no_think else None,
        output=output,
        prompt=PROMPTS[prompt] if output == "json" else None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lectura-eval", description="Score an extraction backend on the labelled set."
    )
    parser.add_argument("-b", "--backend", default="vlm",
                        choices=["vlm", "tesseract", "pix2text"])
    parser.add_argument("-m", "--model", default="qwen2.5vl:7b")
    parser.add_argument("--no-think", action="store_true",
                        help="disable reasoning on models that think by default")
    parser.add_argument("--prompt", default="v1", choices=["v1", "v2"],
                        help="JSON transcription prompt version (see extract/vlm.py)")
    parser.add_argument("--output", default="json", choices=["json", "markdown"],
                        help="markdown for document OCR models such as glm-ocr")
    parser.add_argument("--max-edge", type=int, default=2200)
    parser.add_argument("--no-preprocess", action="store_true")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--cache", type=Path, default=Path("results/raw"),
                        help="raw extraction cache root (default: results/raw)")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cached-only", action="store_true",
                        help="score cached extractions only; never call a model")
    parser.add_argument("--surface", action="append", choices=["notebook", "board", "slide"],
                        help="restrict to one surface (repeatable)")
    parser.add_argument("--refresh", action="store_true",
                        help="discard this configuration's cache before running")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    references = load_all(args.root)
    if not references:
        print(f"no references under {args.root}/pages")
        return 1

    for reference in missing_images(references):
        print(f"skipping {reference.page_id}: image not present ({reference.source})")

    extractor = _extractor(args.backend, args.model, args.no_think, args.output, args.prompt)
    signature = getattr(extractor, "signature", None)
    name = f"{args.backend}-{signature}" if signature else args.backend
    key = f"{name}-{args.max_edge}-{'raw' if args.no_preprocess else 'pre'}"
    cache = None if args.no_cache else args.cache / re.sub(r"[^\w.-]", "_", key)
    if cache and args.refresh and cache.exists():
        shutil.rmtree(cache)

    report = evaluate(
        extractor,
        references,
        max_edge=args.max_edge,
        use_preprocess=not args.no_preprocess,
        cache=cache,
        cached_only=args.cached_only,
        surfaces=set(args.surface) if args.surface else None,
    )

    print(f"{'page':<12}{'CER':>8}{'WER':>8}{'stream':>9}{'exact':>8}")
    for score in report.scores:
        exact = f"{score.formula_exact}/{score.formula_count}"
        print(f"{score.page_id:<12}{score.cer:>8.3f}{score.wer:>8.3f}"
              f"{score.formula_stream_distance:>9.3f}{exact:>8}")
    print(report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
