"""Vision-language model extraction via a local Ollama server.

Deliberately transcription-only: the model is asked to read, not to organise.
Structure inference lives in `structure.py`, because measurements on real
lecture photos showed block typing from the VLM was unreliable even when the
transcription itself was good.
"""

from __future__ import annotations

import base64
import io
import json
import time
import urllib.error
import urllib.request

from PIL import Image

from lectura.extract.base import Extractor, RawExtraction, RawItem

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


class OllamaVLM(Extractor):
    name = "ollama-vlm"

    def __init__(
        self,
        model: str = "qwen2.5vl:7b",
        host: str = DEFAULT_HOST,
        num_ctx: int = 16384,
        timeout: int = 600,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.num_ctx = num_ctx
        self.timeout = timeout

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
            "prompt": PROMPT,
            "images": [base64.b64encode(buf.getvalue()).decode()],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx,
                "num_predict": 4096,
            },
        }

        started = time.perf_counter()
        try:
            body = self._post(payload)
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"cannot reach Ollama at {self.host} - is `ollama serve` running?"
            ) from exc
        elapsed = time.perf_counter() - started

        parsed = _parse(body.get("response", ""))
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
        return RawExtraction(
            items=items,
            title_hint=parsed.get("title"),
            backend=f"{self.name}:{self.model}",
            seconds=round(elapsed, 1),
        )


def _parse(response: str) -> dict:
    response = response.strip()
    if response.startswith("```"):
        parts = response.split("```")
        if len(parts) > 1:
            response = parts[1]
            if response.startswith("json"):
                response = response[4:]
    try:
        parsed = json.loads(response.strip())
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
