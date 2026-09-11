import { useEffect, useRef, useState } from "react";
import { RichText, TeX } from "./TeX";
import { LIST_TYPES, isUncertain, type Block, type BlockType } from "./types";

interface Props {
  block: Block;
  onChange: (block: Block) => void;
  onDelete: () => void;
  onMove: (direction: -1 | 1) => void;
}

const TYPE_LABELS: Record<BlockType, string> = {
  heading: "Heading",
  text: "Text",
  equation: "Equation",
  bullet_list: "Bullets",
  numbered_list: "Numbered",
  definition: "Definition",
  table: "Table",
  diagram: "Diagram",
  code: "Code",
};

export function BlockEditor({ block, onChange, onDelete, onMove }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);

  const isList = LIST_TYPES.includes(block.type);
  const sourceText = isList ? block.items.join("\n") : block.content;

  useEffect(() => {
    if (editing) textarea.current?.focus();
  }, [editing]);

  function open() {
    setDraft(sourceText);
    setEditing(true);
  }

  function commit() {
    const next = isList
      ? { ...block, items: draft.split("\n").filter((line) => line.trim()) }
      : { ...block, content: draft };
    // An edited block is the user's words now, and no longer uncertain.
    onChange({ ...next, origin: "user", flags: [], confidence: null });
    setEditing(false);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") setEditing(false);
    // Enter commits for single-line blocks; lists need real newlines.
    if (event.key === "Enter" && !event.shiftKey && !isList) {
      event.preventDefault();
      commit();
    }
  }

  const classes = [
    "block",
    `block-${block.type}`,
    isUncertain(block) ? "uncertain" : "",
    block.origin === "user" ? "edited" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes}>
      <div className="block-bar">
        <select
          value={block.type}
          onChange={(event) =>
            onChange({ ...block, type: event.target.value as BlockType })
          }
          aria-label="Block type"
        >
          {Object.entries(TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        {isUncertain(block) && (
          <span className="badge badge-warn" title={block.flags.join(", ") || "low confidence"}>
            check
          </span>
        )}
        {block.origin === "user" && <span className="badge">edited</span>}
        {block.confidence !== null && (
          <span className="confidence">{Math.round(block.confidence * 100)}%</span>
        )}
        <span className="spacer" />
        <button onClick={() => onMove(-1)} title="Move up">↑</button>
        <button onClick={() => onMove(1)} title="Move down">↓</button>
        <button onClick={onDelete} title="Delete block">×</button>
      </div>

      {editing ? (
        <div className="editing">
          <textarea
            ref={textarea}
            value={draft}
            rows={isList ? Math.max(3, draft.split("\n").length) : 3}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            spellCheck={block.type !== "equation"}
          />
          {block.type === "equation" && (
            <div className="preview">
              <TeX latex={draft} display />
            </div>
          )}
          <div className="edit-actions">
            <button className="primary" onClick={commit}>Save</button>
            <button onClick={() => setEditing(false)}>Cancel</button>
            <span className="hint">
              {isList ? "one item per line" : "Enter to save, Esc to cancel"}
            </span>
          </div>
        </div>
      ) : (
        <div className="content" onClick={open} title="Click to edit">
          <BlockView block={block} />
        </div>
      )}
    </div>
  );
}

function BlockView({ block }: { block: Block }) {
  if (block.type === "equation") return <TeX latex={block.content} display />;
  if (block.type === "heading") return <h3><RichText text={block.content} /></h3>;
  if (block.type === "bullet_list")
    return <ul>{block.items.map((item, i) => <li key={i}><RichText text={item} /></li>)}</ul>;
  if (block.type === "numbered_list")
    return <ol>{block.items.map((item, i) => <li key={i}><RichText text={item} /></li>)}</ol>;
  if (block.type === "code") return <pre><code>{block.content}</code></pre>;
  return <p><RichText text={block.content} /></p>;
}
