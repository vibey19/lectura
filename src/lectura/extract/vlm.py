"""Vision-language model extraction via a local Ollama server.

Deliberately transcription-only: the model is asked to read, not to organise.
Structure inference lives in `structure.py`, because measurements on real
lecture photos showed block typing from the VLM was unreliable even when the
transcription itself was good.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.request

from PIL import Image

from lectura.extract.base import (
    ExtractionError,
    Extractor,
    RawExtraction,
    RawItem,
)
from lectura.extract.markdown import markdown_items

DEFAULT_HOST = "http://localhost:11434"

PROMPT = """Read this photograph of lecture material (blackboard, whiteboard, \
slide, or handwritten notes).

Transcribe ONLY what is actually written. Do not correct mistakes, do not \
explain, do not add anything that is not visible in the image.

Return JSON:
{"title": <string or null>,
 "lines": [{"text": <transcribed line, LaTeX in $...$ for any mathematics>,
            "kind": "heading"|"body"|"math"|"list_item"|"caption",
            "certain": true|false}]}

Set "certain" to false for anything you are guessing at."""

MARKDOWN_PROMPT = "Text Recognition:"


class OllamaVLM(Extractor):
    name = "ollama-vlm"

    def __init__(
        self,
        model: str = "qwen2.5vl:7b",
        host: str = DEFAULT_HOST,
        num_ctx: int = 16384,
        num_predict: int = 4096,
        timeout: int = 900,
        prompt: str | None = None,
        think: bool | None = None,
        output: str = "json",
    ) -> None:
        if output not in ("json", "markdown"):
            raise ValueError("output must be 'json' or 'markdown'")
        self.model = model
        self.host = host.rstrip("/")
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.timeout = timeout
        # "markdown" is for document OCR models such as GLM-OCR, which take a
        # short task prompt and answer in Markdown with LaTeX, not in JSON.
        self.output = output
        self.prompt = prompt or (PROMPT if output == "json" else MARKDOWN_PROMPT)
        # Reasoning models spend minutes of output budget thinking before they
        # transcribe, and can exhaust num_predict before writing any JSON.
        # None leaves the model's default alone; older models reject the field.
        self.think = think

    @property
    def signature(self) -> str:
        """Identifies everything that changes what the model returns.

        Evaluation caches raw output under this, so editing the prompt cannot
        silently re-score an old prompt's answers as if they were new ones.
        """
        settings = f"{self.prompt}|think={self.think}|predict={self.num_predict}"
        if self.output != "json":   # appended only when set, so existing keys hold
            settings += f"|out={self.output}"
        digest = hashlib.sha1(settings.encode()).hexdigest()[:8]
        return f"{self.model}-{digest}"

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)

    def extract(self, image: Image.Image) -> RawExtraction:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=92)
        payload = {
            "model": self.model,
            "prompt": self.prompt,
            "images": [base64.b64encode(buf.getvalue()).decode()],
            "stream": False,
            "options": {
                # Greedy decoding, deliberately: the evaluation harness depends
                # on extraction being reproducible.
                #
                # It does make the model prone to repetition loops - on one page
                # it emitted "\\bar{x}" 939 times until it ran out of budget,
                # truncating the JSON. A repeat_penalty was tried and measured
                # worse across the board: formula error rose from 0.160 to 0.463
                # and the most notation-dense page went from the best score in
                # the set to reading nothing at all. Valid mathematics *is*
                # repetitive - "\\beta_0 + \\beta_1 x_{i,1} + \\beta_2 x_{i,2}"
                # repeats tokens constantly - so penalising repetition penalises
                # correct LaTeX.
                #
                # Loops are handled after the fact instead: the response is
                # salvaged for whole lines and the note is marked truncated.
                #
                # num_predict doubles as the circuit breaker. Raising it to 8192
                # scored identically on the labelled set - no page legitimately
                # needs that much - while doubling the worst case from about
                # four minutes to nine, because a looping model spends the whole
                # budget. 4096 bounds the damage at no measured cost.
                "temperature": 0,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }

        if self.output == "json":
            payload["format"] = "json"
        if self.think is not None:
            payload["think"] = self.think

        started = time.perf_counter()
        try:
            body = self._post(payload)
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"cannot reach Ollama at {self.host} - is `ollama serve` running?"
            ) from exc
        elapsed = time.perf_counter() - started

        # Ollama reports "length" when the model was cut off mid-answer.
        truncated = body.get("done_reason") == "length"
        if self.output == "markdown":
            items = list(markdown_items(body.get("response", "")))
            if not items:
                raise ExtractionError("the model returned no readable text for this image")
            return RawExtraction(items=items, backend=f"{self.name}:{self.model}",
                                 seconds=round(elapsed, 1), truncated=truncated)

        parsed, salvaged = _parse(body.get("response", ""))
        items = [
            RawItem(
                text=line.get("text", ""),
                # The model's self-reported certainty is coarse and, on our
                # samples, near-always true. Treated as a weak prior only;
                # calibrated confidence is a separate piece of work.
                confidence=0.9 if line.get("certain", True) else 0.4,
                hint=line.get("kind"),
            )
            for line in parsed.get("lines", [])
            if line.get("text")
        ]
        if not items:
            raise ExtractionError(
                "the model returned no readable text for this image"
                + (" before running out of output space" if truncated else "")
            )

        return RawExtraction(
            items=items,
            title_hint=parsed.get("title"),
            backend=f"{self.name}:{self.model}",
            seconds=round(elapsed, 1),
            truncated=truncated or salvaged,
        )


_LINE_OBJECT = re.compile(
    r'\{\s*"text"\s*:\s*"(?P<text>(?:[^"\\]|\\.)*)"\s*,'
    r'\s*"kind"\s*:\s*"(?P<kind>[a-z_]+)"'
    r'(?:\s*,\s*"certain"\s*:\s*(?P<certain>true|false))?\s*\}',
    re.DOTALL,
)
_MAX_REPEATS = 2
_TITLE = re.compile(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _parse(response: str) -> tuple[dict, bool]:
    """Parse the model's JSON, salvaging whole lines if it was cut off.

    Returns the parsed object and whether it had to be salvaged. A truncated
    answer usually contains most of the page followed by a broken final string;
    discarding all of it because the closing brace is missing throws away work
    the user waited minutes for.
    """
    response = response.strip()
    if response.startswith("```"):
        parts = response.split("```")
        if len(parts) > 1:
            response = parts[1]
            if response.startswith("json"):
                response = response[4:]
    response = response.strip()

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return _salvage(response), True
    return (parsed if isinstance(parsed, dict) else {}), False


def _salvage(response: str) -> dict:
    """Recover the complete line objects from a truncated response.

    Consecutive identical lines are collapsed. A response is usually truncated
    because the model looped, and a loop emits *complete* objects - one page
    salvaged into 128 blocks, 120 of them the same expression repeated. Real
    notes do repeat a line occasionally, so a short run is kept and only the
    degenerate tail is dropped.
    """
    lines: list[dict] = []
    repeats = 0
    for match in _LINE_OBJECT.finditer(response):
        line = {
            "text": json.loads(f'"{match.group("text")}"'),
            "kind": match.group("kind"),
            "certain": match.group("certain") != "false",
        }
        if lines and line["text"] == lines[-1]["text"]:
            repeats += 1
            if repeats >= _MAX_REPEATS:
                continue
        else:
            repeats = 0
        lines.append(line)

    title = _TITLE.search(response)
    return {"title": title.group(1) if title else None, "lines": lines}
