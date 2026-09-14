import { useEffect, useRef, useState } from "react";
import { IconCheck, IconDown, IconTrash, IconUp, IconWarn } from "./Icons";
import { RichText, TeX } from "./TeX";
import { applyEdit, blockSource, convertBlock } from "./blocks";
import { LIST_TYPES, isUncertain, type Block, type BlockType } from "./types";

interface Props {
  block: Block;
  active: boolean;
  onFocus: () => void;
  onChange: (block: Block) => void;
  onDelete: () => void;
  onMove: (direction: -1 | 1) => void;
}

const TYPE_LABELS: Record<BlockType, string> = {
  heading: "Heading",
  text: "Paragraph",
  equation: "Equation",
  bullet_list: "Bulleted list",
  numbered_list: "Numbered list",
  definition: "Definition",
  table: "Table",
  diagram: "Diagram",
  code: "Code",
};

export function BlockEditor({ block, active, onFocus, onChange, onDelete, onMove }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);

  const isList = LIST_TYPES.includes(block.type);
  const source = blockSource(block);
  const uncertain = isUncertain(block);

  useEffect(() => {
    if (!editing) return;
    const el = textarea.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, [editing]);

  // A block inserted empty should open ready to type.
  useEffect(() => {
    if (active && !block.content && block.items.length === 0 && !editing) {
      setDraft("");
      setEditing(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  function open() {
    setDraft(source);
    setEditing(true);
    onFocus();
  }

  function commit() {
    const next = applyEdit(block, draft);
    if (next !== block) onChange(next);
    setEditing(false);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") { event.preventDefault(); setEditing(false); return; }
    const withMeta = event.metaKey || event.ctrlKey;
    if (event.key === "Enter" && (withMeta || (!isList && !event.shiftKey))) {
      event.preventDefault();
      commit();
    }
  }

  const classes = [
    "blk",
    `blk-${block.type}`,
    uncertain ? "blk-uncertain" : "",
    block.origin === "user" ? "blk-edited" : "",
    block.origin === "supplement" ? "blk-supplement" : "",
    active ? "blk-active" : "",
    editing ? "blk-editing" : "",
  ].filter(Boolean).join(" ");

  return (
    <section className={classes} onFocus={onFocus}>
      <div className="blk-gutter" aria-hidden="true">
        <span className={`blk-tick blk-tick-${block.type}`} />
      </div>

      <div className="blk-body">
        <div className="blk-bar">
          <label className="select-wrap select-wrap-xs">
            <span className="sr-only">Block type</span>
            <select
              value={block.type}
              onChange={(e) => onChange(convertBlock(block, e.target.value as BlockType))}
            >
              {Object.entries(TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          {/* Colour is never the only signal: each state carries an icon and a word. */}
          {uncertain && (
            <span className="chip chip-warn">
              <IconWarn size={12} /> check
            </span>
          )}
          {uncertain && !editing && (
            // Confirming a reading is not rewriting it: provenance and the
            // model's confidence stay, only the request for review is cleared.
            <button className="chip chip-action" onClick={() => onChange({ ...block, reviewed: true })}
                    title="Mark as checked against the source">
              <IconCheck size={12} /> looks right
            </button>
          )}
          {block.origin === "user" && (
            <span className="chip chip-ok"><IconCheck size={12} /> edited</span>
          )}
          {block.reviewed && block.origin !== "user" && (
            <span className="chip chip-ok"><IconCheck size={12} /> checked</span>
          )}
          {block.confidence !== null && !uncertain && (
            <span className="chip chip-quiet mono">
              {Math.round(block.confidence * 100)}%
            </span>
          )}

          <span className="grow" />
          <button className="icon-btn icon-btn-sm" onClick={() => onMove(-1)}
                  aria-label="Move block up" title="Move up"><IconUp size={14} /></button>
          <button className="icon-btn icon-btn-sm" onClick={() => onMove(1)}
                  aria-label="Move block down" title="Move down"><IconDown size={14} /></button>
          <button className="icon-btn icon-btn-sm icon-btn-danger" onClick={onDelete}
                  aria-label="Delete block" title="Delete"><IconTrash size={14} /></button>
        </div>

        {editing ? (
          <div className="blk-edit">
            <textarea
              ref={textarea}
              value={draft}
              rows={Math.min(14, Math.max(isList ? 4 : 2, draft.split("\n").length + 1))}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              spellCheck={block.type !== "equation" && block.type !== "code"}
              aria-label={`Edit ${TYPE_LABELS[block.type]}`}
              placeholder={isList ? "One item per line" : "Type here"}
            />
            {block.type === "equation" && (
              <div className="blk-preview">
                <span className="blk-preview-label">Preview</span>
                {draft.trim() ? <TeX latex={draft} display /> : <span className="muted">—</span>}
              </div>
            )}
            <div className="blk-actions">
              <button className="btn btn-primary btn-sm" onClick={commit}>Save</button>
              <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>Cancel</button>
              <span className="hint">
                {isList ? "One item per line · ⌘↵ to save" : "↵ to save · Esc to cancel"}
              </span>
            </div>
          </div>
        ) : (
          <div
            className="blk-view"
            onClick={open}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); open(); } }}
            aria-label={`Edit ${TYPE_LABELS[block.type]}`}
          >
            <BlockView block={block} />
          </div>
        )}
      </div>
    </section>
  );
}

function BlockView({ block }: { block: Block }) {
  if (!block.content && block.items.length === 0) {
    return <p className="muted">Empty block — click to write.</p>;
  }
  switch (block.type) {
    case "equation":
      return <TeX latex={block.content} display />;
    case "heading":
      return <h3><RichText text={block.content} /></h3>;
    case "definition":
      return <p className="definition"><RichText text={block.content} /></p>;
    case "bullet_list":
      return <ul>{block.items.map((i, n) => <li key={n}><RichText text={i} /></li>)}</ul>;
    case "numbered_list":
      return <ol>{block.items.map((i, n) => <li key={n}><RichText text={i} /></li>)}</ol>;
    case "code":
      return <pre><code>{block.content}</code></pre>;
    default:
      return <p><RichText text={block.content} /></p>;
  }
}
