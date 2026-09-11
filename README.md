# Lectura

Turn photographs of lecture material — handwritten notes, blackboards, slides —
into structured, editable study notes with correctly rendered mathematics.

Lectura is not an OCR wrapper. It keeps a canonical structured representation of
what a page contained, tracks how confident it is about each piece, and keeps
what was *read from the page* strictly separate from anything the model *added*.

## Status

Working end to end: upload a photo, get structured notes with typeset
mathematics, edit any block, switch themes, export. Smart Supplements and
verification are not built yet.

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
  its `origin`. Generated additions are opt-in and visually distinct — the
  source material is never silently rewritten.
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

Web app:

```bash
uvicorn lectura.api:app --port 8901       # then open http://localhost:8901
```

Upload a photo, click any block to edit it, switch theme, export Markdown.
Editing an equation shows a live preview as you type.

Command line:

```bash
lectura path/to/photo.heic --theme academic
lectura out/photo.json --theme dark        # re-render, no model call
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
pytest                                  # python tests
ruff check .                            # lint
cd frontend && npm install && npm run build   # build the UI into the API
```

The frontend builds into `src/lectura/api/static`, which the API serves. For
frontend work, `npm run dev` proxies API calls to port 8901.

## How good is it?

Measured against hand-written reference transcriptions on four real pages:

| Backend | CER | formula error | exact | time |
|---|---|---|---|---|
| Tesseract | 1.069 | 0.992 | 0/28 | 4s |
| Pix2Text | 0.804 | 0.541 | 1/28 | 15s |
| Qwen2.5-VL 7B | 0.224 | 0.160 | 7/28 | 613s |

Four pages is a small set - enough to catch a large regression, not enough to
settle anything. See ARCHITECTURE.md for what these numbers do and do not say.

## Privacy

Lecture photographs can contain people, names, institutional branding and
copyrighted teaching material. Lectura processes images in memory and stores
nothing by default. Source images are gitignored and never committed.

## Licence

MIT — see LICENSE.
