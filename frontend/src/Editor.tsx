import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { BlockEditor } from "./BlockEditor";
import {
  IconClose, IconDownload, IconImage, IconLayers, IconPlus,
  IconRedo, IconUndo, IconUpload, IconWarn,
} from "./Icons";
import { extract } from "./api";
import { isUncertain, type Block, type BlockType, type Note, type Theme, THEMES } from "./types";

const STORAGE_KEY = "lectura.note.v1";
const HISTORY_LIMIT = 60;

type Status = { kind: "idle" } | { kind: "busy" } | { kind: "error"; message: string };

export default function Editor() {
  const [note, setNoteRaw] = useState<Note | null>(null);
  const [past, setPast] = useState<Note[]>([]);
  const [future, setFuture] = useState<Note[]>([]);
  const [theme, setTheme] = useState<Theme>("academic");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [meta, setMeta] = useState("");
  const [truncated, setTruncated] = useState(false);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [showOutline, setShowOutline] = useState(true);
  const [showSource, setShowSource] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  /* ----------------------------------------------------------- persistence */

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setNoteRaw(JSON.parse(saved));
    } catch {
      /* a corrupt or unavailable store must not block the editor */
    }
  }, []);

  useEffect(() => {
    if (!note) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(note));
    } catch {
      /* private browsing, quota, blocked storage: not worth interrupting for */
    }
  }, [note]);

  /* --------------------------------------------------------------- history */

  const commit = useCallback(
    (next: Note) => {
      setNoteRaw((current) => {
        if (current) setPast((p) => [...p.slice(-HISTORY_LIMIT), current]);
        setFuture([]);
        return next;
      });
    },
    [],
  );

  const undo = useCallback(() => {
    setPast((p) => {
      if (p.length === 0) return p;
      const previous = p[p.length - 1];
      setNoteRaw((current) => {
        if (current) setFuture((f) => [current, ...f]);
        return previous;
      });
      return p.slice(0, -1);
    });
  }, []);

  const redo = useCallback(() => {
    setFuture((f) => {
      if (f.length === 0) return f;
      const [next, ...rest] = f;
      setNoteRaw((current) => {
        if (current) setPast((p) => [...p, current]);
        return next;
      });
      return rest;
    });
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const meta_ = event.metaKey || event.ctrlKey;
      if (!meta_ || event.key.toLowerCase() !== "z") return;
      // Let the browser handle undo inside a field being edited.
      const el = document.activeElement;
      if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) return;
      event.preventDefault();
      event.shiftKey ? redo() : undo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo]);

  /* ---------------------------------------------------------------- upload */

  const upload = useCallback(async (file: File) => {
    setStatus({ kind: "busy" });
    try {
      const result = await extract(file);
      setPast([]);
      setFuture([]);
      setNoteRaw(result.note);
      // The server returns the corrected image it read, which the browser can
      // always display; the raw upload is frequently HEIC and cannot be shown.
      setSourceUrl(result.preview);
      setTruncated(result.truncated);
      setMeta(`${result.backend} · ${result.seconds}s`);
      setStatus({ kind: "idle" });
      setShowSource(true);
    } catch (error) {
      setStatus({ kind: "error", message: (error as Error).message });
    }
  }, []);

  /* ----------------------------------------------------------- block edits */

  function updateBlock(index: number, block: Block) {
    if (!note) return;
    const blocks = [...note.blocks];
    blocks[index] = block;
    commit({ ...note, blocks });
  }

  function deleteBlock(index: number) {
    if (!note) return;
    commit({ ...note, blocks: note.blocks.filter((_, i) => i !== index) });
  }

  function moveBlock(index: number, direction: -1 | 1) {
    if (!note) return;
    const target = index + direction;
    if (target < 0 || target >= note.blocks.length) return;
    const blocks = [...note.blocks];
    [blocks[index], blocks[target]] = [blocks[target], blocks[index]];
    commit({ ...note, blocks });
  }

  function insertBlock(index: number, type: BlockType = "text") {
    if (!note) return;
    const block: Block = {
      id: `new-${Date.now().toString(36)}`,
      type, content: "", items: [], level: null,
      origin: "user", confidence: null, bbox: null,
      source_image: null, flags: [],
    };
    const blocks = [...note.blocks];
    blocks.splice(index, 0, block);
    commit({ ...note, blocks });
    setActiveId(block.id);
  }

  /* --------------------------------------------------------------- derived */

  const uncertain = useMemo(
    () => (note ? note.blocks.filter((b) => isUncertain(b)) : []),
    [note],
  );

  const wordCount = useMemo(() => {
    if (!note) return 0;
    return note.blocks.reduce((total, block) => {
      const text = [block.content, ...block.items].join(" ");
      return total + text.split(/\s+/).filter(Boolean).length;
    }, 0);
  }, [note]);

  function exportMarkdown() {
    if (!note) return;
    const blob = new Blob([toMarkdown(note)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${(note.title ?? "notes").replace(/[^\w -]/g, "")}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function scrollToBlock(id: string) {
    setActiveId(id);
    document.getElementById(`block-${id}`)?.scrollIntoView({
      behavior: "smooth", block: "center",
    });
  }

  /* ------------------------------------------------------------------ view */

  return (
    <div className="editor" data-theme={theme}>
      <header className="toolbar">
        <Link to="/" className="brand brand-sm" aria-label="Lectura home">
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="5" fill="var(--accent)" />
            <path d="M8 8.5h8M8 12h8M8 15.5h4.5" stroke="var(--accent-ink)"
                  strokeWidth="1.7" strokeLinecap="round" />
          </svg>
          <span>Lectura</span>
        </Link>

        <div className="toolbar-title">
          {note && (
            <input
              className="title-input"
              value={note.title ?? ""}
              placeholder="Untitled notes"
              aria-label="Note title"
              onChange={(e) => commit({ ...note, title: e.target.value })}
            />
          )}
        </div>

        <div className="toolbar-actions">
          <button className="icon-btn" onClick={undo} disabled={past.length === 0}
                  aria-label="Undo" title="Undo (⌘Z)"><IconUndo /></button>
          <button className="icon-btn" onClick={redo} disabled={future.length === 0}
                  aria-label="Redo" title="Redo (⇧⌘Z)"><IconRedo /></button>
          <span className="divider" />
          <button className={`icon-btn ${showOutline ? "on" : ""}`}
                  onClick={() => setShowOutline((v) => !v)}
                  aria-pressed={showOutline} aria-label="Toggle outline"
                  title="Outline"><IconLayers /></button>
          <button className={`icon-btn ${showSource ? "on" : ""}`}
                  onClick={() => setShowSource((v) => !v)}
                  disabled={!sourceUrl} aria-pressed={showSource}
                  aria-label="Toggle source image" title="Source image"><IconImage /></button>
          <span className="divider" />
          <label className="select-wrap">
            <span className="sr-only">Theme</span>
            <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
              {THEMES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <button className="btn btn-ghost btn-sm" onClick={() => fileInput.current?.click()}>
            <IconUpload size={15} /> Upload
          </button>
          <button className="btn btn-primary btn-sm" onClick={exportMarkdown} disabled={!note}>
            <IconDownload size={15} /> Export
          </button>
        </div>
      </header>

      <input ref={fileInput} type="file" accept="image/*,.heic,.HEIC" hidden
             onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} />

      <div className="workspace">
        {note && showOutline && (
          <aside className="rail" aria-label="Document outline">
            <div className="rail-head">Outline</div>
            <ol className="outline">
              {note.blocks.map((block) => (
                <li key={block.id}>
                  <button
                    className={`outline-item ${activeId === block.id ? "active" : ""}`}
                    onClick={() => scrollToBlock(block.id)}
                  >
                    <span className={`dot dot-${block.type}`} aria-hidden="true" />
                    <span className="outline-text">
                      {preview(block) || <em>empty</em>}
                    </span>
                    {isUncertain(block) && <IconWarn size={12} />}
                  </button>
                </li>
              ))}
            </ol>
          </aside>
        )}

        <main className="canvas">
          {!note && status.kind === "idle" && (
            <Dropzone
              dragging={dragging}
              setDragging={setDragging}
              onFile={upload}
              onBrowse={() => fileInput.current?.click()}
            />
          )}

          {status.kind === "busy" && <Skeleton />}

          {status.kind === "error" && (
            <div className="notice notice-error" role="alert">
              <IconWarn size={18} />
              <div>
                <strong>Could not read that image.</strong>
                <p>{status.message}</p>
              </div>
              <button className="btn btn-ghost btn-sm"
                      onClick={() => setStatus({ kind: "idle" })}>Dismiss</button>
            </div>
          )}

          {note && status.kind !== "busy" && (
            <>
              {truncated && (
                <div className="notice notice-warn" role="status">
                  <IconWarn size={18} />
                  <div>
                    <strong>This page was cut short.</strong>
                    <p>
                      The model ran out of room before finishing, so the end of
                      the page is missing. What it did read is below.
                    </p>
                  </div>
                </div>
              )}
              {uncertain.length > 0 && (
                <div className="notice notice-warn">
                  <IconWarn size={18} />
                  <div>
                    <strong>{uncertain.length} block{uncertain.length > 1 ? "s" : ""} to check.</strong>
                    <p>Recognition was unsure here. Compare against the source image.</p>
                  </div>
                  <button className="btn btn-ghost btn-sm"
                          onClick={() => scrollToBlock(uncertain[0].id)}>Go to first</button>
                </div>
              )}

              <article className="paper">
                <InsertHere onInsert={() => insertBlock(0)} />
                {note.blocks.map((block, index) => (
                  <div key={block.id} id={`block-${block.id}`}>
                    <BlockEditor
                      block={block}
                      active={activeId === block.id}
                      onFocus={() => setActiveId(block.id)}
                      onChange={(next) => updateBlock(index, next)}
                      onDelete={() => deleteBlock(index)}
                      onMove={(direction) => moveBlock(index, direction)}
                    />
                    <InsertHere onInsert={() => insertBlock(index + 1)} />
                  </div>
                ))}
              </article>

              <footer className="statusbar">
                <span>{note.blocks.length} blocks</span>
                <span>{wordCount} words</span>
                {meta && <span className="mono">{meta}</span>}
                <span className="grow" />
                <span>Saved locally</span>
              </footer>
            </>
          )}
        </main>

        {note && showSource && sourceUrl && (
          <aside className="source" aria-label="Source image">
            <div className="rail-head">
              Source
              <button className="icon-btn icon-btn-sm" onClick={() => setShowSource(false)}
                      aria-label="Hide source image"><IconClose size={14} /></button>
            </div>
            <div className="source-scroll">
              <img src={sourceUrl} alt="The photograph these notes were read from" />
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- pieces */

function Dropzone({ dragging, setDragging, onFile, onBrowse }: {
  dragging: boolean;
  setDragging: (v: boolean) => void;
  onFile: (file: File) => void;
  onBrowse: () => void;
}) {
  return (
    <div
      className={`dropzone ${dragging ? "over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) onFile(file);
      }}
      onClick={onBrowse}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onBrowse(); }}
    >
      <IconUpload size={26} />
      <h2>Drop a photo of lecture material</h2>
      <p>Handwritten notes, a blackboard, or a slide — HEIC, JPEG or PNG.</p>
      <span className="btn btn-primary">Choose a photo</span>
    </div>
  );
}

/** Skeleton rather than a spinner: it reserves the space the note will occupy,
 *  so nothing jumps when the result lands. */
function Skeleton() {
  return (
    <div className="paper skeleton" aria-busy="true" aria-live="polite">
      <p className="sr-only">Reading the page</p>
      <div className="sk sk-title" />
      <div className="sk sk-line" style={{ width: "88%" }} />
      <div className="sk sk-line" style={{ width: "74%" }} />
      <div className="sk sk-eq" />
      <div className="sk sk-line" style={{ width: "81%" }} />
      <div className="sk sk-line" style={{ width: "60%" }} />
      <div className="sk sk-eq" />
      <div className="sk sk-line" style={{ width: "70%" }} />
      <p className="skeleton-note">
        Reading the page — a full-resolution photo takes about a minute.
      </p>
    </div>
  );
}

function InsertHere({ onInsert }: { onInsert: () => void }) {
  return (
    <div className="insert">
      <button className="insert-btn" onClick={onInsert} aria-label="Insert a block here">
        <IconPlus size={14} />
      </button>
    </div>
  );
}

const GREEK: Record<string, string> = {
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", theta: "θ",
  lambda: "λ", mu: "μ", pi: "π", rho: "ρ", sigma: "σ", tau: "τ", phi: "φ",
  omega: "ω", Delta: "Δ", Sigma: "Σ", Omega: "Ω", partial: "∂", sum: "Σ",
  int: "∫", sqrt: "√", infty: "∞", times: "×", cdot: "·", pm: "±",
  leq: "≤", geq: "≥", neq: "≠", approx: "≈", rightarrow: "→", log: "log",
};

/** A short, readable label for the outline.
 *
 *  Stripping LaTeX commands wholesale leaves orphaned subscript markers, so
 *  "\\mu_i = \\beta_0" became "_i = _0". Commands are mapped to their symbol
 *  where one exists and to their bare name otherwise. */
function preview(block: Block): string {
  const source = block.content || block.items[0] || "";
  return source
    .replace(/\\([a-zA-Z]+)/g, (_, name: string) => GREEK[name] ?? name)
    .replace(/[{}$]/g, "")
    .replace(/\^\s*/g, "^")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 44);
}

function toMarkdown(note: Note): string {
  const lines: string[] = [];
  if (note.title) lines.push(`# ${note.title}`, "");
  for (const block of note.blocks) {
    switch (block.type) {
      case "heading": lines.push(`${"#".repeat(block.level ?? 2)} ${block.content}`, ""); break;
      case "equation": lines.push("$$", block.content, "$$", ""); break;
      case "bullet_list": lines.push(...block.items.map((i) => `- ${i}`), ""); break;
      case "numbered_list": lines.push(...block.items.map((i, n) => `${n + 1}. ${i}`), ""); break;
      case "code": lines.push("```", block.content, "```", ""); break;
      default: lines.push(block.content, "");
    }
  }
  return lines.join("\n");
}
