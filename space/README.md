---
title: Lectura
emoji: 📝
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: 6.27.0
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
short_description: Lecture photos into structured notes with typeset maths
---

# Lectura

The reading service behind [Lectura](https://github.com/vibey19/lectura): a photo
of handwritten notes, a blackboard or a slide goes in, and a structured note with
LaTeX mathematics comes out.

It runs [GLM-OCR](https://huggingface.co/zai-org/GLM-OCR) (MIT) on ZeroGPU,
followed by Lectura's own perspective and lighting correction, structuring and
post-processing. Images are processed in memory and not stored.
