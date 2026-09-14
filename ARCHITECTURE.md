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
| Preprocess | `preprocess.py` | page detection, dewarp, illumination |
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
generated addition the user accepted, `user` is hand-authored. Because it lives
in the data rather than in a convention, the separation between source material
and generated augmentation cannot be quietly lost.

**Blocks point back at the image.** A normalised bounding box means the interface
can always show the user what a block was derived from, which is what makes an
uncertain transcription reviewable instead of merely doubtful. No backend fills
the box in yet - the VLM is asked for text only - so this is the contract the
interface is built against rather than something it can show today.

A third field, `reviewed`, records that a person checked a block against the
source and accepted it. It is kept apart from origin: confirming a transcription
is not writing it, so the block stays `extracted` and keeps the model's
confidence, and only the request for review is cleared.

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

Layout inside a formula is normalised away before either comparison: spacing
and sizing commands, and the `aligned` wrapper with its `&` and `\\` that the
structuring stage uses to line up derivation steps. Matrix separators are kept,
because a transposed matrix is a genuine misreading.

`lectura-eval` runs a backend over the set. Each page's raw extraction is
cached under `results/raw/`, one directory per backend configuration, so a
change to structuring or scoring is re-measured in well under a second rather
than by another model pass. Every structuring change since has been checked
against all three backends that way.

## Backend comparison

Four labelled pages, raw input at 2200px, identical metric, re-measured after
structuring learned to recognise bare sub- and superscripts and to join
derivation steps:

| Backend | CER | formula error | exact | time |
|---|---|---|---|---|
| Tesseract | 1.058 | 0.997 | 0/28 | 2s |
| Pix2Text | 0.689 | 0.510 | 1/28 | 8s |
| Qwen2.5-VL 7B | **0.225** | **0.159** | **7/28** | 294s |

The VLM row is reproducible to the third decimal: a fresh run matched the first
measurement within 0.001. Wall-clock times roughly halved against the first
measurement on the same machine, from newer runtimes rather than from anything
in this repository, so compare times within a table, not across tables.

Tesseract's formula error is 0.997 - nothing recoverable, scoring exactly 1.000
on three of four pages. Its CER of 1.912 on the derivatives page is worse than
emitting nothing at all, because it invents more wrong characters than the page
contains.

Pix2Text splits exactly along the line this project was founded on. Its formula
error is roughly half Tesseract's, so the formula recogniser does work on
handwriting, while its text stays poor: it recovered the square-root
and fraction structure of an expression while reading the heading above it as
"P R O B / E M-3". It is a formula specialist, not a whole-page baseline for
this material. Its CER fell from 0.811 to 0.689 when structuring started
recognising lines like `x_{i,1}` as notation, which says as much about the
earlier scoring as about Pix2Text: subscripted expressions had been counted as
badly read prose.

The VLM wins on both axes by a wide margin and loses on latency by roughly 40x.
That gap is a design input rather than a defect: a router that sends clean
printed material to the fast staged pipeline and handwriting to the VLM is the
obvious way to keep a free-tier demo responsive.

Per-page numbers matter more than the averages. The VLM scores 0.022 formula
error on dense symbolic algebra and 0.395 on a page of numeric substitution.
Reading the raw output for that page shows why, and it is not the digits: the
model wrote no LaTeX at all, giving `w1 * x + b1` for `w_1 \cdot x + b_1` and
`1 / (1 + e^-x)` for a fraction, while reading the values themselves correctly.
It does the same on the mostly-prose page, where one formula hides it, and uses
LaTeX on 25 of 31 lines across the two notation-heavy pages. Simple notation
gets written the way one would type it. That is a prompting and model-choice
problem, not a structuring one, and it is the first thing to test on any
replacement model.

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

## When the model loops

Greedy decoding is used so extraction is reproducible, which the evaluation
harness depends on. It also makes the model prone to repetition loops: on one
page it read ten lines correctly, reached a formula, and emitted `\bar{x}` 939
times until it exhausted its output budget, truncating the JSON mid-string.

Three things were tried.

**A repetition penalty made it worse.** Formula error rose from 0.160 to 0.463
and the most notation-dense page in the set went from the best score to reading
nothing at all. The reason is structural: valid mathematics *is* repetitive -
`\beta_0 + \beta_1 x_{i,1} + \beta_2 x_{i,2}` repeats tokens constantly - so
penalising repetition penalises correct LaTeX. Reverted.

**A larger output budget bought nothing.** Doubling `num_predict` scored
identically, because no page legitimately needs that length, while doubling the
worst case from four minutes to nine: a looping model spends whatever it is
given. The modest budget stays, as a circuit breaker.

**Salvage works.** A truncated response holds most of the page followed by one
broken string, so complete line objects are recovered by pattern and the note is
marked truncated. The page that previously produced nothing now yields ten
blocks and its title, and the interface says the page was cut short.

The general lesson, on its third instance: every intervention that treats
mathematical notation as ordinary text damages it. Contrast enhancement
thickened thin strokes and turned every mu into an M; ruling suppression lifted
faint pen strokes along with printed grid; repetition penalty punished
legitimately repetitive LaTeX. All three looked obviously correct beforehand and
were caught only by measurement.

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
