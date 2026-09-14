"""`lectura-label`: write reference transcriptions for the evaluation set.

    lectura-label                           # photos in "handwritten notes/"
    lectura-label path/to/boards --surface board --licence "Public domain"

Opens a local page showing one unlabelled photo beside a form: prose in reading
order, and one LaTeX expression per line with a live preview. Saving writes
`data/eval/pages/<id>.json` and moves to the next photo.

The page never shows what any model read. A reference corrected from model
output inherits that model's mistakes and then scores them as right, which is
the one thing an evaluation set must not do.
"""

from __future__ import annotations

import argparse
import io
import json
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from lectura import ingest
from lectura.evaluate.dataset import DEFAULT_ROOT, Reference, load_all

SURFACES = ("notebook", "board", "slide")
PAGE = Path(__file__).with_name("label.html")


class Submission(BaseModel):
    page_id: str
    surface: str
    text: str
    formulas: list[str]
    licence: str
    note: str = ""


def _images(folder: Path) -> dict[str, Path]:
    return {
        path.stem: path
        for path in sorted(folder.iterdir())
        if path.suffix.lower() in ingest.SUPPORTED
    }


def create_app(folder: Path, root: Path, surface: str, licence: str) -> FastAPI:
    app = FastAPI(title="lectura-label")
    images = _images(folder)

    def queue() -> list[str]:
        done = {reference.page_id for reference in load_all(root)}
        return [page_id for page_id in images if page_id not in done]

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text().replace("__DEFAULTS__", json.dumps(
            {"surface": surface, "licence": licence, "surfaces": SURFACES}
        ))

    @app.get("/api/queue")
    def pending() -> dict:
        return {"pending": queue(), "labelled": len(images) - len(queue())}

    @app.get("/image/{page_id}")
    def image(page_id: str) -> Response:
        path = images.get(page_id)   # only ids from the folder listing, never a path
        if path is None:
            raise HTTPException(404, "no such image")
        picture = ingest.fit_within(ingest.load(path), 2000)
        buffer = io.BytesIO()
        picture.save(buffer, format="JPEG", quality=88)
        return Response(buffer.getvalue(), media_type="image/jpeg")

    @app.post("/api/save")
    def save(submission: Submission) -> dict:
        path = images.get(submission.page_id)
        if path is None:
            raise HTTPException(404, "no such image")
        if submission.surface not in SURFACES:
            raise HTTPException(400, f"surface must be one of {', '.join(SURFACES)}")
        try:
            source = str(path.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            source = str(path.resolve())
        reference = Reference(
            page_id=submission.page_id,
            source=source,
            surface=submission.surface,
            text=" ".join(submission.text.split()),
            formulas=[f.strip() for f in submission.formulas if f.strip()],
            licence=submission.licence.strip() or "personal",
            note=submission.note.strip(),
        )
        saved = reference.save(root)
        return {"saved": str(saved), "remaining": len(queue())}

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lectura-label", description=__doc__.split("\n")[0])
    parser.add_argument("folder", type=Path, nargs="?", default=Path("handwritten notes"))
    parser.add_argument("--surface", default="notebook", choices=SURFACES)
    parser.add_argument("--licence", default="personal")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--port", type=int, default=8902)
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"no such folder: {args.folder}")
        return 1

    import uvicorn

    url = f"http://127.0.0.1:{args.port}"
    print(f"labelling {args.folder} -> {args.root}/pages   open {url}   (Ctrl+C to stop)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app = create_app(args.folder, args.root, args.surface, args.licence)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
