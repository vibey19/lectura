import type { Note } from "./types";

/** Everything that belongs to one open note, and so moves with it through
 *  undo. The preview and the truncation warning used to live in separate state,
 *  so undoing past an upload - or reloading the page - paired a note with the
 *  wrong photograph or none at all. */
export interface Doc {
  note: Note;
  /** Image the note was read from: a data URL for uploads, a path for examples. */
  preview: string | null;
  truncated: boolean;
  /** Short provenance line for the status bar, e.g. "ollama-vlm · 42s". */
  meta: string;
}

export interface History {
  doc: Doc | null;
  past: Doc[];
  future: Doc[];
}

export type HistoryAction =
  /** Open a different note. Undoable, so a new upload never destroys the last. */
  | { kind: "open"; doc: Doc }
  /** Replace the note's content with an edited version. */
  | { kind: "edit"; note: Note }
  | { kind: "undo" }
  | { kind: "redo" }
  /** Rehydrate from storage. Not an action the user took, so no history. */
  | { kind: "restore"; doc: Doc };

export const HISTORY_LIMIT = 60;

export const emptyHistory: History = { doc: null, past: [], future: [] };

function push(past: Doc[], doc: Doc | null): Doc[] {
  return doc ? [...past, doc].slice(-HISTORY_LIMIT) : past;
}

/** Pure, so React may call it twice (StrictMode does) without doubling history.
 *  The previous version pushed onto the undo stack from inside a state updater,
 *  which is exactly the kind of side effect StrictMode replays. */
export function historyReducer(state: History, action: HistoryAction): History {
  switch (action.kind) {
    case "open":
      return { doc: action.doc, past: push(state.past, state.doc), future: [] };
    case "edit":
      if (!state.doc || state.doc.note === action.note) return state;
      return {
        doc: { ...state.doc, note: action.note },
        past: push(state.past, state.doc),
        future: [],
      };
    case "undo": {
      if (state.past.length === 0) return state;
      const previous = state.past[state.past.length - 1];
      return {
        doc: previous,
        past: state.past.slice(0, -1),
        future: state.doc ? [state.doc, ...state.future] : state.future,
      };
    }
    case "redo": {
      if (state.future.length === 0) return state;
      const [next, ...rest] = state.future;
      return { doc: next, past: push(state.past, state.doc), future: rest };
    }
    case "restore":
      return { doc: action.doc, past: [], future: [] };
  }
}

const STORAGE_KEY = "lectura.doc.v2";
const LEGACY_KEY = "lectura.note.v1";

export function loadStoredDoc(): Doc | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved) as Doc;
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy) return { note: JSON.parse(legacy) as Note, preview: null, truncated: false, meta: "" };
  } catch {
    /* a corrupt or unavailable store must not block the editor */
  }
  return null;
}

export function storeDoc(doc: Doc): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(doc));
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // Most likely the quota: an uploaded preview is a data URL of a few hundred
    // kilobytes. Keeping the note matters more than keeping its picture.
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...doc, preview: null }));
    } catch {
      /* private browsing or blocked storage: not worth interrupting for */
    }
  }
}
