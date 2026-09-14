# Evaluation set

Hand-checked ground truth for extraction quality. One JSON file per page in
`pages/`, holding what a careful reader sees on that page.

**Images are not committed.** They are personal coursework or third-party lecture
material; each reference records where its image came from and under what
licence, so the set is reproducible without redistributing anything.

## Conventions

- `text` is prose in reading order, **excluding** mathematics. Text and formulas
  are scored separately because they fail differently.
- `formulas` is LaTeX in reading order. Continuation lines are merged into the
  expression they continue: `z = wx + b`, `= (-2)·1 + 2`, `= 0` is recorded as
  one expression, because that is the statement a reader sees.
- The primary formula score concatenates every expression on each side and
  compares the two token streams, so where line breaks fall does not count.
  Exact match is also reported, and that one is positional: a missed equation
  shifts everything after it, which is deliberate - a dropped formula is a real
  failure.
- Run `lectura-eval` to score a backend against these pages.

## Adding a page

Read the image carefully and write the reference by hand. Never paste model
output in as ground truth; the point of this set is to be independent of any
model.
