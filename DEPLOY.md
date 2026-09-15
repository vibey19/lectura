# Deploying

The frontend and backend deploy separately, because they have incompatible
requirements: the frontend is static files, and the backend needs to run a
5.6 GB vision model for minutes per request.

## Why not all on Vercel

Vercel runs serverless functions. Extraction needs a GPU-class machine, weights
far larger than the bundle limit, and 25-500 seconds per request against a
timeout of 60 seconds (300 on Pro). The frontend belongs there; the model does
not.

## The demo works without a backend

`frontend/public/demo/` holds pre-baked notes — real extraction output from real
pages, not cleaned up. They load instantly as static files, so the deployed site
is fully explorable with no backend at all: open a note, edit blocks, switch
themes, export.

This is the path most visitors should take. Live upload is the secondary route,
and the interface says so when the backend is unreachable.

## Frontend → Vercel

```bash
cd frontend
npm run build:static      # writes dist/
```

Vercel settings:

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Build command | `npm run build:static` |
| Output directory | `dist` |
| Environment | `VITE_API_URL` = backend origin, or unset for examples only |

Leaving `VITE_API_URL` unset ships an examples-only demo. That is a reasonable
place to start: it always works, and it costs nothing to run.

## Backend → any host that allows long requests

A Docker image is provided. It runs Ollama alongside the API and pulls the model
on first boot, so the image stays small enough to build on free tiers at the
cost of a slow first request.

```bash
docker build -t lectura .
docker run -p 7860:7860 \
  -e LECTURA_ALLOWED_ORIGINS=https://your-site.vercel.app \
  lectura
```

| Variable | Default | Purpose |
|---|---|---|
| `LECTURA_MODEL` | `glm-ocr` | Ollama model to serve |
| `LECTURA_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |
| `LECTURA_RATE_LIMIT` | `12` | Extractions per client per hour; 0 disables |
| `LECTURA_TRUSTED_PROXIES` | `0` | Reverse proxies in front of the API; see below |
| `PORT` | `7860` | Hugging Face Spaces expects 7860 |

### Behind a proxy

The rate limit identifies clients by address. `X-Forwarded-For` is ignored by
default, because a client can put anything in it. Behind a platform proxy -
Hugging Face Spaces, a load balancer, nginx - every request appears to come
from the proxy, so set `LECTURA_TRUSTED_PROXIES` to the number of proxies in
the chain (usually `1`). The limit then uses the address your own proxy
recorded and ignores anything the client added in front of it. Left at `0`
behind a proxy, the limit still holds but is shared by all visitors.

### On free CPU hosting, be realistic

A 7B vision model with no GPU takes many minutes per page. The rate limit exists
because each request occupies a core for that long, and a public endpoint doing
minutes of work per call is otherwise someone else's free compute.

If live extraction matters more than the €0 constraint, a GPU-backed Space is
the lever to pull. Otherwise ship the examples and keep the backend for local
use.

## Checklist

- [ ] `npm run build:static` succeeds
- [ ] `frontend/public/demo/index.json` lists the examples
- [ ] `VITE_API_URL` set, or deliberately left unset
- [ ] `LECTURA_ALLOWED_ORIGINS` includes the deployed frontend origin
- [ ] Rate limit appropriate for the host
- [ ] `LECTURA_TRUSTED_PROXIES` matches the proxies in front of the API
