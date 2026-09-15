"""GLM-OCR through Hugging Face Transformers.

The same model the benchmark measured through Ollama, loaded directly so it can
run on a GPU host such as a Hugging Face ZeroGPU Space, where there is no Ollama.
Its answer is Markdown with LaTeX and is read exactly as the Ollama path reads
it, including collapsing a page the model wrote out twice.

`generate` can be injected. On ZeroGPU the function that touches the GPU must
carry the `@spaces.GPU` decorator, and that decorator belongs to the Space, not
to this library.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PIL import Image

from lectura.extract.base import (
    ExtractionError,
    Extractor,
    RawExtraction,
    collapse_repeated_blocks,
)
from lectura.extract.markdown import markdown_items

MODEL_ID = "zai-org/GLM-OCR"
PROMPT = "Text Recognition:"


def load(
    model_id: str = MODEL_ID,
    device: str | None = None,
    dtype: str | None = None,
    attention: str | None = None,
):
    """Load processor and model. Imported lazily: torch is not a core dependency.

    `dtype` and `attention` are exposed so the hosted demo can be checked
    against the benchmark. Scored on the notebook pages, the Space in float32
    matched the Ollama build that was measured (formula error 0.123 against
    0.124) while individual symbols still differ now and then - it read one
    board's h-bar as pi where Ollama did not.
    """
    import torch
    from transformers import AutoProcessor, GlmOcrForConditionalGeneration

    if device is None:
        device = (
            "cuda" if torch.cuda.is_available()
            else "mps" if torch.backends.mps.is_available()
            else "cpu"
        )
    if dtype is None:
        dtype = "bfloat16" if device != "cpu" else "float32"
    processor = AutoProcessor.from_pretrained(model_id)
    extra = {"attn_implementation": attention} if attention else {}
    model = GlmOcrForConditionalGeneration.from_pretrained(
        model_id, dtype=getattr(torch, dtype), **extra
    ).to(device)
    model.eval()
    return processor, model


def make_generate(processor, model, max_new_tokens: int = 4096) -> Callable[[Image.Image], str]:
    """A function from image to the model's raw Markdown answer."""

    def generate(image: Image.Image) -> str:
        import torch

        messages = [{
            "role": "user",
            "content": [{"type": "image", "image": image}, {"type": "text", "text": PROMPT}],
        }]
        inputs = processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt",
        ).to(model.device)
        with torch.inference_mode():
            # Greedy, as elsewhere: reproducible output is what makes the
            # evaluation meaningful. max_new_tokens is the loop circuit breaker.
            output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        new_tokens = output[0][inputs["input_ids"].shape[1]:]
        return processor.decode(new_tokens, skip_special_tokens=True)

    return generate


class GlmOcrTransformers(Extractor):
    name = "glm-ocr-transformers"

    def __init__(self, generate: Callable[[Image.Image], str] | None = None) -> None:
        self._generate = generate

    @property
    def signature(self) -> str:
        return f"{MODEL_ID.replace('/', '_')}-transformers"

    def extract(self, image: Image.Image) -> RawExtraction:
        if self._generate is None:
            self._generate = make_generate(*load())
        started = time.perf_counter()
        answer = self._generate(image)
        elapsed = time.perf_counter() - started

        items = collapse_repeated_blocks(list(markdown_items(answer)))
        if not items:
            raise ExtractionError("the model returned no readable text for this image")
        return RawExtraction(
            items=items, backend=f"glm-ocr:{MODEL_ID}", seconds=round(elapsed, 1)
        )
