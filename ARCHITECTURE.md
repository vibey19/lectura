# Architecture

## The finding that shaped the design

Two measurements on real lecture material drove every decision below.

**Classical OCR fails on mathematics, not on handwriting.** Tesseract, run over a
set of handwritten study pages, produced usable text from prose written in the
same hand that defeated it entirely a page later. The variable was notation
density: fractions, roots, subscripted indices and matrices reduced output to
noise, while paragraphs came through readable.

**A vision-language model reads the material well but organises it badly.** The
same pages, given to a 7B open-weights VLM, produced correct LaTeX for
handwritten expressions — including subscripted regression terms. But asked in
the same breath to assign document structure, it typed three-line derivations as
plain text, shattered numbered lists into loose lines, and reported perfect
confidence on a matrix it had transcribed with a wrong row.

So: trust the model to *read*, do not trust it to *organise*, and never trust its
self-reported certainty.

## Pipeline

```
image ──► ingest ──► preprocess ──► extract ──► structure ──► Note
                                       │                        │
                                   (VLM / OCR)          verify ──┤
                                                        augment ─┤
                                                                 ▼
                                                    render · export · edit
```

| Stage | Module | Responsibility |
|---|---|---|
| Ingest | `ingest.py` | HEIC decode, EXIF rotation, resolution policy |
| Preprocess | `preprocess.py` | page detection, dewarp, illumination — *planned* |
| Extract | `extract/` | transcription only, behind one interface |
| Structure | `structure.py` | typed blocks, list merging, heading detection |
| Verify | `verify.py` | flags doubt; never edits — *planned* |
| Augment | `augment.py` | opt-in supplements — *planned* |
| Render | `render/` | themes, export |

### Why extraction and structuring are separate modules

This is the direct consequence of the second measurement. Asking one call to read
handwriting *and* infer document structure yields the first well and the second
badly, and leaves no way to fix the second without perturbing the first.

Splitting them means structuring operates on text alone: deterministic, unit
testable, and correctable in minutes rather than by prompt archaeology. Every
structuring rule in `structure.py` has a test pinning a real failure observed on
real pages.

### Why extractors sit behind one interface

`Extractor` is a protocol returning `RawExtraction`. Tesseract and the VLM
implement it identically, so the baseline stays runnable rather than becoming a
story about a script someone deleted. Any claim that the system improved on
classical OCR can be re-measured with a flag.

## The Note model

`schema.py` is the contract. Renderers, exporters and the editor consume it;
nothing downstream invents its own shape.

Two invariants:

**Origin is tracked per block.** `extracted` came off the page, `supplement` is an
AI addition the user accepted, `user` is hand-authored. Because it lives in the
data rather than in a convention, the separation between source material and AI
augmentation cannot be quietly lost.

**Blocks point back at the image.** A normalised bounding box means the interface
can always show the user what a block was derived from, which is what makes an
uncertain transcription reviewable instead of merely doubtful.

## Confidence

Blocks carry an optional confidence and a list of flags. Absent confidence means
*unknown*, never *good* — Tesseract supplies none, and that must not read as
high confidence.

The VLM's self-reported certainty is currently used as a weak prior only. It
reported every block as certain across the entire sample set, including
demonstrably wrong output, so it carries almost no information. Deriving
calibrated confidence from decoder token probabilities, validated against
measured error, is planned work.

## Resolution as the latency lever

Inference cost scales with pixel count, not content difficulty:

| Input | Resolution | Time |
|---|---|---|
| Video frame | 640×480 | 18–26 s |
| Phone photo | 1237×2200 | 67–125 s |

Hence `--max-edge`. The intended end state is two-pass: detect regions cheaply at
low resolution, then re-read only mathematical regions at full resolution, paying
for detail solely where it changes the answer.

## Deliberately absent

No database, no accounts, no server-side image storage. Notes are files. This
keeps the privacy story simple — nothing is retained — and removes an entire
infrastructure tier from a project that does not yet need one.
