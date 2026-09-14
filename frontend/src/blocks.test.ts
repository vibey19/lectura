import { describe, expect, it } from "vitest";
import { applyEdit, convertBlock, outlineLabel, toMarkdown } from "./blocks";
import type { Block, Note } from "./types";

function block(overrides: Partial<Block>): Block {
  return {
    id: "b1", type: "text", content: "", items: [], level: null,
    origin: "extracted", confidence: 0.4, bbox: null, source_image: null,
    flags: ["low_confidence"], ...overrides,
  };
}

describe("convertBlock", () => {
  it("keeps a list's items when it becomes a paragraph", () => {
    const list = block({ type: "bullet_list", items: ["first", "second"] });
    const text = convertBlock(list, "text");
    expect(text.content).toBe("first\nsecond");
    expect(text.items).toEqual([]);
    expect(toMarkdown({ title: null, blocks: [text] } as unknown as Note)).toContain("first");
  });

  it("splits a paragraph into items when it becomes a list", () => {
    const text = block({ content: "one\n\n two \nthree" });
    expect(convertBlock(text, "numbered_list").items).toEqual(["one", "two", "three"]);
  });

  it("moves between list styles without touching the items", () => {
    const list = block({ type: "bullet_list", items: ["a", "b"] });
    expect(convertBlock(list, "numbered_list").items).toEqual(["a", "b"]);
  });

  it("gives headings a level and takes it away again", () => {
    const heading = convertBlock(block({ content: "Title" }), "heading");
    expect(heading.level).toBe(2);
    expect(convertBlock(heading, "text").level).toBeNull();
  });

  it("is a structural fix, so provenance is untouched", () => {
    const converted = convertBlock(block({ content: "x" }), "equation");
    expect(converted.origin).toBe("extracted");
    expect(converted.confidence).toBe(0.4);
  });
});

describe("applyEdit", () => {
  it("returns the same block when the text did not change", () => {
    const original = block({ content: "read off the page" });
    expect(applyEdit(original, "read off the page  ")).toBe(original);
    const list = block({ type: "bullet_list", items: ["a", "b"] });
    expect(applyEdit(list, "a\nb\n")).toBe(list);
  });

  it("marks real changes as the user's and drops the model's doubt", () => {
    const edited = applyEdit(block({ content: "M" }), "\\mu");
    expect(edited.origin).toBe("user");
    expect(edited.flags).toEqual([]);
    expect(edited.confidence).toBeNull();
  });
});

describe("outlineLabel", () => {
  it("substitutes symbols and drops layout commands", () => {
    expect(outlineLabel(block({ content: "\\frac{\\mu_i}{2}" }))).toBe("μ_i2");
  });

  it("does not show alignment markup", () => {
    const aligned = block({ content: "\\begin{aligned} z &= 1 \\\\ &= 0 \\end{aligned}" });
    expect(outlineLabel(aligned)).toBe("z = 1 = 0");
  });
});
