import type { ExtractResponse, Note, Theme } from "./types";

export async function extract(
  file: File,
  options: { backend?: string; maxEdge?: number; preprocess?: boolean } = {},
): Promise<ExtractResponse> {
  const { backend = "vlm", maxEdge = 2200, preprocess = true } = options;
  const body = new FormData();
  body.append("file", file);

  const query = new URLSearchParams({
    backend,
    max_edge: String(maxEdge),
    use_preprocess: String(preprocess),
  });

  const response = await fetch(`/api/extract?${query}`, { method: "POST", body });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail ?? "extraction failed");
  }
  return response.json();
}

export async function renderNote(note: Note, theme: Theme): Promise<string> {
  const response = await fetch("/api/render", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note, theme }),
  });
  if (!response.ok) throw new Error("render failed");
  return response.text();
}
