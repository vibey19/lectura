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

## Evaluation

`evaluate/` holds a labelled set and the metrics that score against it. Ground
truth is written by reading the page, never by accepting model output.

Text and mathematics are scored separately and never blended. The founding
observation of this project is that classical OCR degrades with mathematical
density while leaving prose intact; a single averaged number would conceal
exactly that, and in practice CER has stayed flat across changes that moved
formula accuracy by a factor of five.

The primary formula metric is a **segmentation-independent** token edit distance:
every expression on each side is concatenated and the two streams compared. A
positional metric was tried first and scored a page at 0.895 - near-total
failure - purely because the reference merged a three-line derivation that the
model emitted as three lines. The same page scores 0.395 once line breaks stop
counting as errors. A metric that punishes formatting will send you optimising
the wrong thing.

Positional exact-match is kept as a strict secondary signal.

## Backend comparison

Four labelled pages, raw input at 2200px, identical metric:

| Backend | CER | formula error | exact | time |
|---|---|---|---|---|
| Tesseract | 1.069 | 0.992 | 0/28 | 4s |
| Pix2Text | 0.804 | 0.541 | 1/28 | 15s |
| Qwen2.5-VL 7B | **0.224** | **0.160** | **7/28** | 613s |

Tesseract's formula error is 0.992 - nothing recoverable, scoring exactly 1.000
on three of four pages. Its CER of 1.903 on the derivatives page is worse than
emitting nothing at all, because it invents more wrong characters than the page
contains.

Pix2Text splits exactly along the line this project was founded on. Its formula
error is roughly half Tesseract's, so the formula recogniser does work on
handwriting, while its text CER barely improves: it recovered the square-root
and fraction structure of an expression while reading the heading above it as
"P R O B / E M-3". It is a formula specialist, not a whole-page baseline for
this material.

The VLM wins on both axes by a wide margin and loses on latency by roughly 40x.
That gap is a design input rather than a defect: a router that sends clean
printed material to the fast staged pipeline and handwriting to the VLM is the
obvious way to keep a free-tier demo responsive.

Per-page numbers matter more than the averages. The VLM scores 0.022 formula
error on dense symbolic algebra and 0.395 on a page of numeric substitution -
the hard case is arithmetic with small digits, not mathematics with large
notation, which is the opposite of what one would guess.

## What preprocessing is measured to do

Page detection went from 1 of 19 real photos to 19 of 19 when edge detection was
replaced with brightness segmentation, and the corrected images are plainly
better to look at. Neither of those is an accuracy claim.

Scored against reference transcriptions, preprocessing does **not** improve
extraction. The best configuration measured roughly ties raw input:

| Configuration | formula error | CER | exact |
|---|---|---|---|
| raw | 0.208 | 0.236 | 6/19 |
| dewarp only | 0.321 | 0.504 | 6/19 |
| dewarp + illumination | 0.224 | 0.230 | 6/19 |
| dewarp + ruling | 0.370 | 0.504 | 0/19 |
| everything | 0.273 | 0.230 | 0/19 |

Illumination correction earns its place: it halves CER in both configurations
containing it. Ruling suppression consistently costs formula accuracy and is now
opt-in. The default chain is dewarp plus illumination.

Preprocessing's real benefit is that it makes a lower input resolution
tolerable, worth about 30% of wall-clock time, and it is a precondition for
handling curved pages. It is not an accuracy win.

Two pages is enough to catch a five-fold regression. It is not enough to settle
anything, and these numbers should be re-measured as the set grows.

One thing it did do was cause a regression. CLAHE contrast enhancement turned
every handwritten mu on a statistics page into a capital M - twelve occurrences,
silently, with full reported confidence. An ablation isolated it to that single
step, and contrast is now opt-in.

That failure is the argument for the next piece of work. Block counts and
character totals cannot distinguish "read the page correctly" from "produced a
similar volume of plausible text"; only a diff against reference transcriptions
caught it. Until a labelled test set exists, changes to this pipeline cannot be
evaluated, only admired.

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
