"""Lectura on a Hugging Face ZeroGPU Space.

Serves one API endpoint, `/extract`, that the Lectura web app calls: a photo in,
a structured note out. The model runs on a shared GPU only while a page is being
read; everything else - decoding, perspective and lighting correction,
structuring - runs on the Space's CPU through the same `lectura.pipeline` the
local server uses.
"""

from __future__ import annotations

import os
from pathlib import Path

import gradio as gr
import spaces
import torch

from lectura import ingest
from lectura.extract.base import ExtractionError
from lectura.extract.glm_transformers import GlmOcrTransformers, load, make_generate
from lectura.pipeline import read_image

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# ZeroGPU attaches a GPU per call; the weights are placed on "cuda" once at start.
# Precision and attention are Space variables, so they can be compared by
# restarting the Space rather than rebuilding it.
processor, model = load(
    device="cuda" if torch.cuda.is_available() else None,
    dtype=os.getenv("LECTURA_DTYPE") or None,
    attention=os.getenv("LECTURA_ATTENTION") or None,
)
_generate = make_generate(processor, model)


@spaces.GPU(duration=120)
def generate_on_gpu(image):
    return _generate(image)


extractor = GlmOcrTransformers(generate=generate_on_gpu)


def extract(photo: str | None, use_preprocess: bool = False) -> dict:
    if not photo:
        raise gr.Error("Choose a photo first.")
    path = Path(photo)
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise gr.Error("That image is larger than 20 MB.")
    try:
        image = ingest.decode(path.read_bytes())
    except OSError as exc:
        raise gr.Error(f"Could not read that image: {exc}") from exc
    try:
        result = read_image(image, extractor, use_preprocess=use_preprocess,
                            source_name=path.name)
    except ExtractionError as exc:
        raise gr.Error(str(exc)) from exc
    body = result.model_dump(mode="json")
    body["backend"] += f" ({model.dtype}, {model.config._attn_implementation})"
    return body


with gr.Blocks(title="Lectura") as demo:
    gr.Markdown(
        "# Lectura\n"
        "Photographs of lecture notes, blackboards and slides into structured notes "
        "with typeset mathematics. This Space is the reading service behind the "
        "Lectura web app; try it here or use the app for editing and export."
    )
    photo = gr.File(label="Photo", file_types=["image", ".heic", ".heif"], type="filepath")
    # Off by default: measured on the Space, correction raised GLM-OCR's formula
    # error on the notebook pages from 0.123 to 0.144.
    use_preprocess = gr.Checkbox(value=False, label="Correct perspective and lighting")
    read = gr.Button("Read the page", variant="primary")
    note = gr.JSON(label="Note")
    read.click(extract, inputs=[photo, use_preprocess], outputs=note, api_name="extract")

demo.queue(max_size=16).launch()
