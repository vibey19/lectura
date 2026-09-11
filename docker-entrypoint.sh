#!/usr/bin/env bash
set -euo pipefail

ollama serve &

# Wait for the daemon before pulling; a cold container is not ready instantly.
for _ in $(seq 1 60); do
  curl -sf "http://${OLLAMA_HOST}/api/version" >/dev/null 2>&1 && break
  sleep 1
done

if ! ollama list | grep -q "${LECTURA_MODEL%%:*}"; then
  echo "pulling ${LECTURA_MODEL} (several GB, first boot only)"
  ollama pull "${LECTURA_MODEL}"
fi

exec uvicorn lectura.api:app --host 0.0.0.0 --port "${PORT}"
