import type { ExtractResponse, Note, Theme } from "./types";

/** Base URL for the API.
 *
 *  Empty in local development and on a single-origin deployment, where the
 *  server also serves the frontend. Set to the backend's origin when the two
 *  are deployed separately - a static host cannot run a 6GB vision model, so
 *  splitting them is the normal arrangement rather than the exception.
 */
export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

/** Whether a live backend is configured at all. Without one the app is still
 *  fully usable through the pre-baked examples. */
export const HAS_BACKEND = API_BASE !== "" || import.meta.env.DEV ||
  (typeof window !== "undefined" && window.location.port === "8901");

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function failure(response: Response): Promise<ApiError> {
  const fallback = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    return new ApiError(body.detail ?? fallback, response.status);
  } catch {
    return new ApiError(fallback, response.status);
  }
}

export interface Health {
  status: string;
  themes: string[];
  backends: string[];
}

/** Is the backend awake? Free hosting sleeps, so this is asked before offering
 *  upload rather than letting the user wait on a request that cannot succeed. */
export async function health(timeoutMs = 6000): Promise<Health | null> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}/api/health`, { signal: abort.signal });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function extract(
  file: File,
  options: {
    backend?: string;
    maxEdge?: number;
    preprocess?: boolean;
    signal?: AbortSignal;
  } = {},
): Promise<ExtractResponse> {
  const { backend = "vlm", maxEdge = 2200, preprocess = true, signal } = options;
  const body = new FormData();
  body.append("file", file);

  const query = new URLSearchParams({
    backend,
    max_edge: String(maxEdge),
    use_preprocess: String(preprocess),
  });

  const response = await fetch(`${API_BASE}/api/extract?${query}`, {
    method: "POST",
    body,
    signal,
  });
  if (!response.ok) throw await failure(response);
  return response.json();
}

export async function renderNote(note: Note, theme: Theme): Promise<string> {
  const response = await fetch(`${API_BASE}/api/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note, theme }),
  });
  if (!response.ok) throw await failure(response);
  return response.text();
}

export interface DemoEntry {
  slug: string;
  title: string;
  blurb: string;
  blocks: number;
  seconds: number;
  truncated: boolean;
}

/** Pre-baked notes, served as static files so the demo works with no backend. */
export async function demoIndex(): Promise<DemoEntry[]> {
  const response = await fetch("/demo/index.json");
  return response.ok ? response.json() : [];
}

export async function demoNote(slug: string): Promise<{ note: Note; preview: string }> {
  const response = await fetch(`/demo/${slug}.json`);
  if (!response.ok) throw new ApiError("example not found", 404);
  return { note: await response.json(), preview: `/demo/${slug}.jpg` };
}
