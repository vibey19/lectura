import { useCallback, useMemo, useRef, useState } from "react";
import { extract } from "./api";
import { BlockEditor } from "./BlockEditor";
import { THEMES, isUncertain, type Block, type Note, type Theme } from "./types";

type Status = { kind: "idle" } | { kind: "busy" } | { kind: "error"; message: string };

export default function App() {
  const [note, setNote] = useState<Note | null>(null);
  const [meta, setMeta] = useState<string>("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [theme, setTheme] = useState<Theme>("academic");
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const uncertainCount = useMemo(
    () => note?.blocks.filter(isUncertain).length ?? 0,
    [note],
  );

  const upload = useCallback(async (file: File) => {
    setStatus({ kind: "busy" });
    try {
      const result = await extract(file);
      setNote(result.note);
      setMeta(`${result.backend} · ${result.seconds}s · ${result.preprocess}`);
      setStatus({ kind: "idle" });
    } catch (error) {
      setStatus({ kind: "error", message: (error as Error).message });
    }
  }, []);

  function onDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void upload(file);
  }

  function updateBlock(index: number, block: Block) {
    if (!note) return;
    const blocks = [...note.blocks];
    blocks[index] = block;
    setNote({ ...note, blocks });
  }

  function deleteBlock(index: number) {
    if (!note) return;
    setNote({ ...note, blocks: note.blocks.filter((_, i) => i !== index) });
  }

  function moveBlock(index: number, direction: -1 | 1) {
    if (!note) return;
    const target = index + direction;
    if (target < 0 || target >= note.blocks.length) return;
    const blocks = [...note.blocks];
    [blocks[index], blocks[target]] = [blocks[target], blocks[index]];
    setNote({ ...note, blocks });
  }

  function download(filename: string, content: string, mime: string) {
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function exportMarkdown() {
    if (!note) return;
    download(`${note.title ?? "notes"}.md`, toMarkdown(note), "text/markdown");
  }

  return (
    <div className="app" data-theme={theme}>
      <header>
        <h1>Lectura</h1>
        <div className="controls">
          <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
            {THEMES.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          <button onClick={() => input.current?.click()}>Upload</button>
          <button onClick={exportMarkdown} disabled={!note}>Export</button>
        </div>
      </header>

      <input
        ref={input}
        type="file"
        accept="image/*,.heic,.HEIC"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void upload(file);
        }}
      />

      {!note && status.kind !== "busy" && (
        <div
          className={`dropzone ${dragging ? "over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => input.current?.click()}
        >
          <p className="big">Drop a photo of lecture material</p>
          <p className="small">
            handwritten notes, a blackboard, or a slide · HEIC, JPEG or PNG
          </p>
        </div>
      )}

      {status.kind === "busy" && (
        <div className="dropzone busy">
          <p className="big">Reading the page…</p>
          <p className="small">
            a full-resolution photo takes about a minute on this machine
          </p>
        </div>
      )}

      {status.kind === "error" && (
        <div className="error">
          <strong>Extraction failed.</strong> {status.message}
        </div>
      )}

      {note && (
        <main>
          <div className="note-meta">
            <h2>{note.title ?? "Untitled notes"}</h2>
            <span className="meta">{meta}</span>
            {uncertainCount > 0 && (
              <span className="badge badge-warn">
                {uncertainCount} to check
              </span>
            )}
          </div>
          <div className="blocks">
            {note.blocks.map((block, index) => (
              <BlockEditor
                key={block.id}
                block={block}
                onChange={(next) => updateBlock(index, next)}
                onDelete={() => deleteBlock(index)}
                onMove={(direction) => moveBlock(index, direction)}
              />
            ))}
          </div>
        </main>
      )}
    </div>
  );
}

function toMarkdown(note: Note): string {
  const lines: string[] = [];
  if (note.title) lines.push(`# ${note.title}`, "");
  for (const block of note.blocks) {
    switch (block.type) {
      case "heading":
        lines.push(`${"#".repeat(block.level ?? 2)} ${block.content}`, "");
        break;
      case "equation":
        lines.push("$$", block.content, "$$", "");
        break;
      case "bullet_list":
        lines.push(...block.items.map((item) => `- ${item}`), "");
        break;
      case "numbered_list":
        lines.push(...block.items.map((item, i) => `${i + 1}. ${item}`), "");
        break;
      case "code":
        lines.push("```", block.content, "```", "");
        break;
      default:
        lines.push(block.content, "");
    }
  }
  return lines.join("\n");
}
