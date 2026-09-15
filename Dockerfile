# Backend image: FastAPI plus a local Ollama serving the vision model.
#
# The frontend is deployed separately to a static host. This image exists
# because a 5.6GB model cannot run on serverless functions - no GPU, a bundle
# size limit far below the weights, and an execution timeout well under the
# time a single page takes.

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .

ENV LECTURA_MODEL=glm-ocr \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_KEEP_ALIVE=10m \
    PORT=7860

# Weights are pulled on first boot rather than baked in: it keeps the image
# small enough to build on free tiers, at the cost of a slow first request.
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 7860
ENTRYPOINT ["docker-entrypoint.sh"]
