# Lectura

Turn photographs of lecture material — handwritten notes, blackboards, slides —
into structured, editable study notes with correctly rendered mathematics.

Lectura is not an OCR wrapper. It keeps a canonical structured representation of
what a page contained, tracks how confident it is about each piece, and keeps
what was *read from the page* strictly separate from anything AI *added*.

## Status

Early. The extraction pipeline and renderer work end to end from the command
line; the web UI, editor and supplements are not built yet.

## Why

Standard OCR fails on lecture material in a specific way. Measured on a set of
real handwritten pages, Tesseract degraded with **mathematical density**, not
handwriting quality:

| Page content | Tesseract result |
|---|---|
| Mostly prose, print handwriting | Usable, minor errors |
| Prose with light notation | Headings survive, body degrades |
| Dense derivations | Mostly collapse |
| Pure algebra (roots, fractions, subscripts) | Total failure — 7 junk tokens from a full page |

A vision-language model reads the same pages far better, including correct LaTeX
for handwritten expressions. But it has failure modes of its own, which shape the
design (see ARCHITECTURE.md).

## Design commitments

- **One canonical note model.** Themes, exports and the editor are views over
  the same structure. Switching theme never re-runs a model.
- **Extraction, verification and augmentation are separate.** Every block records
  its `origin`. AI additions are opt-in and visually distinct — the source
  material is never silently rewritten.
- **Uncertainty is part of the product.** Blocks carry confidence and warning
  flags, and the interface surfaces doubtful blocks for review rather than
  presenting everything as equally trustworthy.
- **No paid inference API.** Everything runs on open weights.

## Install

Requires Python 3.11+ and [Ollama](https://ollama.com) for the vision model.

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
ollama pull qwen2.5vl:7b
```

Tesseract (the baseline backend) is optional: `brew install tesseract`.

## Use

```bash
lectura path/to/photo.heic --theme academic
```

Writes a structured `.json` note and a rendered `.html` file to `./out`.

```
Options
  -t, --theme      academic | dark | minimal | notebook
  -b, --backend    vlm (default) | tesseract (baseline)
  -m, --model      Ollama model name (default: qwen2.5vl:7b)
      --max-edge   downscale longest edge; the main latency lever
```

Latency scales with pixel count, not content difficulty — roughly 20s for a
small frame and 80–125s for a full-resolution phone photo on an M4.

## Development

```bash
pytest          # tests
ruff check .    # lint
```

## Privacy

Lecture photographs can contain people, names, institutional branding and
copyrighted teaching material. Lectura processes images in memory and stores
nothing by default. Source images are gitignored and never committed.

## Licence

MIT — see LICENSE.
