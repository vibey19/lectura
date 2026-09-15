import type { ExtractResponse, Note, Theme } from "./types";

/** Base URL for the API.
 *
 *  Empty in local development and on a single-origin deployment, where the
 *  server also serves the frontend. Set to the backend's origin when the two
 *  are deployed separately - a static host cannot run a 6GB vision model, so
 *  splitting them is the normal arrangement rather than the exception.
 */
export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

/** Hugging Face Space that runs the model on a GPU. The deployed site reads
 *  photos through it; the local API remains the path for development. */
export const HF_SPACE = import.meta.env.VITE_HF_SPACE ?? "";

/** Whether a live backend is configured at all. Without one the app is still
 *  fully usable through the pre-baked examples. */
export const HAS_BACKEND = HF_SPACE !== "" || API_BASE !== "" || import.meta.env.DEV ||
  (typeof window !== "undefined" && window.location.port === "8901");

/** The Gradio client is loaded only when a photo is actually read, so visitors
 *  who only browse the examples never download it. */
async function space() {
  const { Client, handle_file } = await import("@gradio/client");
  return { client: await Client.connect(HF_SPACE), handle_file };
}

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
  if (HF_SPACE) {
    // A Space that is building or has crashed fails to connect; a sleeping one
    // wakes on connect, which can take longer than a plain health check.
    const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs * 3));
    const connected = space()
      .then(() => ({ status: "ok", themes: [], backends: ["glm-ocr"] }))
      .catch(() => null);
    return Promise.race([connected, timeout]);
  }
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

  if (HF_SPACE) {
    let result: { data: unknown };
    try {
      const { client, handle_file } = await space();
      result = await client.predict("/extract", {
        photo: handle_file(file),
        use_preprocess: preprocess,
      });
    } catch (error) {
      // Gradio reports gr.Error messages - "Choose a photo first", a model
      // failure, an exhausted GPU quota - as the error's message.
      const message = (error as { message?: string })?.message;
      throw new ApiError(message || "The reading service could not be reached.", 503);
    }
    // The client cannot cancel a queued job, so a cancelled read is dropped here.
    if (signal?.aborted) throw new DOMException("cancelled", "AbortError");
    return (result.data as ExtractResponse[])[0];
  }

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
  /** Where the photograph came from. Public domain still deserves provenance. */
  credit?: string;
  licence?: string;
  source?: string;
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
