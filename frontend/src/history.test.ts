import { describe, expect, it } from "vitest";
import { type Doc, emptyHistory, historyReducer } from "./history";
import type { Note } from "./types";

const note = (title: string) => ({ title, blocks: [] }) as unknown as Note;
const doc = (title: string, preview = `${title}.jpg`): Doc =>
  ({ note: note(title), preview, truncated: false, meta: "" });

describe("historyReducer", () => {
  it("makes opening a new note undoable, photograph included", () => {
    let state = historyReducer(emptyHistory, { kind: "open", doc: doc("first") });
    state = historyReducer(state, { kind: "open", doc: doc("second") });
    state = historyReducer(state, { kind: "undo" });
    expect(state.doc?.note.title).toBe("first");
    expect(state.doc?.preview).toBe("first.jpg");
    state = historyReducer(state, { kind: "redo" });
    expect(state.doc?.preview).toBe("second.jpg");
  });

  it("is pure, so a doubled call in StrictMode cannot double the history", () => {
    const start = historyReducer(emptyHistory, { kind: "open", doc: doc("a") });
    const action = { kind: "edit", note: note("b") } as const;
    historyReducer(start, action);
    expect(historyReducer(start, action).past).toHaveLength(1);
  });

  it("clears redo on a fresh edit and ignores no-op edits", () => {
    let state = historyReducer(emptyHistory, { kind: "open", doc: doc("a") });
    state = historyReducer(state, { kind: "edit", note: note("b") });
    state = historyReducer(state, { kind: "undo" });
    expect(state.future).toHaveLength(1);
    state = historyReducer(state, { kind: "edit", note: note("c") });
    expect(state.future).toHaveLength(0);
    expect(historyReducer(state, { kind: "edit", note: state.doc!.note })).toBe(state);
  });

  it("does not record restoring from storage as a step", () => {
    const state = historyReducer(emptyHistory, { kind: "restore", doc: doc("saved") });
    expect(state.past).toHaveLength(0);
  });
});
