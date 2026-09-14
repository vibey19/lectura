import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { BlockEditor } from "./BlockEditor";
import { outlineLabel, toMarkdown } from "./blocks";
import {
  IconClose, IconDownload, IconImage, IconLayers, IconPlus,
  IconRedo, IconUndo, IconUpload, IconWarn,
} from "./Icons";
import {
  ApiError, HAS_BACKEND, demoIndex, demoNote, extract, health,
  type DemoEntry,
} from "./api";
import { downscale } from "./downscale";
import { emptyHistory, historyReducer, loadStoredDoc, storeDoc } from "./history";
import { isUncertain, type Block, type BlockType, type Note, type Theme, THEMES } from "./types";

type Status = { kind: "idle" } | { kind: "busy" } | { kind: "error"; message: string };

export default function Editor() {
  const [history, dispatch] = useReducer(historyReducer, emptyHistory);
  const { doc, past, future } = history;
  const note = doc?.note ?? null;
  const sourceUrl = doc?.preview ?? null;
  const [theme, setTheme] = useState<Theme>("academic");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [showOutline, setShowOutline] = useState(true);
  const [showSource, setShowSource] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [examples, setExamples] = useState<DemoEntry[]>([]);
  const [backendUp, setBackendUp] = useState<boolean | null>(HAS_BACKEND ? null : false);
  const [elapsed, setElapsed] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const inflight = useRef<AbortController | null>(null);

  /* ----------------------------------------------------------- persistence */

  useEffect(() => {
    const stored = loadStoredDoc();
    if (stored) dispatch({ kind: "restore", doc: stored });
  }, []);

  useEffect(() => {
    if (doc) storeDoc(doc);
  }, [doc]);

  useEffect(() => {
    void demoIndex().then(setExamples);
    if (HAS_BACKEND) void health().then((h) => setBackendUp(h !== null));
  }, []);

  // Elapsed seconds during extraction: a request that can run for minutes needs
  // to look alive, not hung.
  useEffect(() => {
    if (status.kind !== "busy") return;
    setElapsed(0);
    const timer = setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, [status.kind]);

  /* --------------------------------------------------------------- history */

  const commit = useCallback((next: Note) => dispatch({ kind: "edit", note: next }), []);
  const undo = useCallback(() => dispatch({ kind: "undo" }), []);
  const redo = useCallback(() => dispatch({ kind: "redo" }), []);

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

  const openExample = useCallback(async (slug: string) => {
    try {
      const { note: loaded, preview } = await demoNote(slug);
      dispatch({ kind: "open", doc: { note: loaded, preview, truncated: false, meta: "example" } });
      setShowSource(true);
      setStatus({ kind: "idle" });
    } catch (error) {
      setStatus({ kind: "error", message: (error as Error).message });
    }
  }, []);

  const upload = useCallback(async (raw_file: File) => {
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    setStatus({ kind: "busy" });
    try {
      const file = await downscale(raw_file);
      const result = await extract(file, { signal: controller.signal });
      // The server returns the corrected image it read, which the browser can
      // always display; the raw upload is frequently HEIC and cannot be shown.
      // Opening is undoable, so a new upload never destroys the previous note.
      dispatch({
        kind: "open",
        doc: {
          note: result.note,
          preview: result.preview,
          truncated: result.truncated,
          meta: `${result.backend} · ${result.seconds}s`,
        },
      });
      setStatus({ kind: "idle" });
      setShowSource(true);
    } catch (error) {
      if (controller.signal.aborted) { setStatus({ kind: "idle" }); return; }
      const message =
        error instanceof ApiError
          ? error.message
          : "The server could not be reached. It may be asleep — try an example below.";
      setStatus({ kind: "error", message });
    } finally {
      if (inflight.current === controller) inflight.current = null;
    }
  }, []);

  const cancel = useCallback(() => inflight.current?.abort(), []);

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
            <TitleInput
              value={note.title ?? ""}
              onCommit={(title) => commit({ ...note, title: title || null })}
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
                      {outlineLabel(block) || <em>empty</em>}
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
            <>
              <Dropzone
                dragging={dragging}
                setDragging={setDragging}
                onFile={upload}
                onBrowse={() => fileInput.current?.click()}
                backendUp={backendUp}
              />
              {examples.length > 0 && (
                <Examples entries={examples} onOpen={openExample} />
              )}
            </>
          )}

          {status.kind === "busy" && <Skeleton elapsed={elapsed} onCancel={cancel} />}

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
              {doc?.truncated && (
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
                {doc?.meta && <span className="mono">{doc.meta}</span>}
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

function Dropzone({ dragging, setDragging, onFile, onBrowse, backendUp }: {
  dragging: boolean;
  setDragging: (v: boolean) => void;
  onFile: (file: File) => void;
  onBrowse: () => void;
  backendUp: boolean | null;
}) {
  const offline = backendUp === false;
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
      {offline && (
        <p className="dropzone-offline">
          Live reading is offline right now — the examples below work without it.
        </p>
      )}
    </div>
  );
}

function Examples({ entries, onOpen }: {
  entries: DemoEntry[];
  onOpen: (slug: string) => void;
}) {
  return (
    <section className="examples">
      <h3>Or open a finished example</h3>
      <p className="examples-lede">
        Real output from public-domain blackboard photographs — not cleaned up,
        so you can see where it is unsure.
      </p>
      <div className="example-grid">
        {entries.map((entry) => (
          <button key={entry.slug} className="example" onClick={() => onOpen(entry.slug)}>
            <img src={`/demo/${entry.slug}.jpg`} alt="" loading="lazy" />
            <span className="example-title">{entry.title}</span>
            <span className="example-blurb">{entry.blurb}</span>
            <span className="example-meta mono">{entry.blocks} blocks</span>
            {entry.credit && (
              <span className="example-credit">
                {entry.credit} · {entry.licence}
              </span>
            )}
          </button>
        ))}
      </div>
    </section>
  );
}

/** Skeleton rather than a spinner: it reserves the space the note will occupy,
 *  so nothing jumps when the result lands. */
function Skeleton({ elapsed, onCancel }: { elapsed: number; onCancel: () => void }) {
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
        Reading the page — {elapsed}s elapsed. A full-resolution photo usually
        takes about a minute.
        <button className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
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

/** The title commits when editing finishes rather than on every keystroke,
 *  which filled the undo history with one entry per letter typed. */
function TitleInput({ value, onCommit }: { value: string; onCommit: (title: string) => void }) {
  const [draft, setDraft] = useState(value);
  const cancelled = useRef(false);
  useEffect(() => setDraft(value), [value]);   // follow undo and newly opened notes

  const finish = () => {
    if (cancelled.current) { cancelled.current = false; return; }
    const title = draft.trim();
    if (title !== value) onCommit(title);
  };

  return (
    <input
      className="title-input"
      value={draft}
      placeholder="Untitled notes"
      aria-label="Note title"
      onChange={(e) => setDraft(e.target.value)}
      onBlur={finish}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") {
          cancelled.current = true;
          setDraft(value);
          e.currentTarget.blur();
        }
      }}
    />
  );
}
