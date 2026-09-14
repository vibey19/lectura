import { LIST_TYPES, type Block, type BlockType, type Note } from "./types";

const isList = (type: BlockType) => LIST_TYPES.includes(type);

/** Change a block's type without losing what it says.
 *
 *  Lists keep their text in `items`, everything else in `content`. Switching
 *  between the two used to change only the label, so a list turned into a
 *  paragraph rendered empty while its items sat invisibly in the data - and
 *  export, which reads `content` for paragraphs, dropped them. The text now
 *  moves with the type: one item per line either way.
 *
 *  Re-typing is a structural correction, not a rewrite of what the page said,
 *  so origin, confidence and flags are left alone.
 */
export function convertBlock(block: Block, type: BlockType): Block {
  if (type === block.type) return block;

  let { content, items } = block;
  if (isList(block.type) && !isList(type)) {
    content = items.join("\n");
    items = [];
  } else if (!isList(block.type) && isList(type)) {
    items = content.split("\n").map((line) => line.trim()).filter(Boolean);
    content = "";
  }

  const level = type === "heading" ? block.level ?? 2 : null;
  return { ...block, type, content, items, level };
}

/** The editable text of a block, as it appears in the textarea. */
export function blockSource(block: Block): string {
  return isList(block.type) ? block.items.join("\n") : block.content;
}

/** Apply edited text to a block. Returns the block unchanged if the text is.
 *
 *  Opening a block and saving without touching it used to mark it as written
 *  by the user and discard the model's confidence, so extracted text was
 *  relabelled as authored merely by being looked at.
 */
export function applyEdit(block: Block, draft: string): Block {
  const next = isList(block.type)
    ? { ...block, items: draft.split("\n").map((line) => line.trim()).filter(Boolean) }
    : { ...block, content: draft.trim() };

  const unchanged = isList(block.type)
    ? next.items.join("\n") === block.items.join("\n")
    : next.content === block.content;
  if (unchanged) return block;

  // Edited content is the user's now: it is no longer a model guess, so the
  // warning flags and the model's confidence no longer describe it.
  return { ...next, origin: "user", flags: [], confidence: null, reviewed: false };
}

const SYMBOLS: Record<string, string> = {
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", zeta: "ζ",
  eta: "η", theta: "θ", kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ",
  pi: "π", rho: "ρ", sigma: "σ", tau: "τ", phi: "φ", chi: "χ", psi: "ψ",
  omega: "ω", Delta: "Δ", Gamma: "Γ", Lambda: "Λ", Phi: "Φ", Pi: "Π",
  Sigma: "Σ", Omega: "Ω", Theta: "Θ",
  partial: "∂", nabla: "∇", sum: "Σ", prod: "Π", int: "∫", sqrt: "√",
  infty: "∞", times: "×", cdot: "·", pm: "±", mp: "∓", div: "÷",
  leq: "≤", geq: "≥", neq: "≠", approx: "≈", equiv: "≡", propto: "∝",
  in: "∈", subset: "⊂", cup: "∪", cap: "∩", forall: "∀", exists: "∃",
  rightarrow: "→", leftarrow: "←", leftrightarrow: "↔", Rightarrow: "⇒",
  to: "→", mapsto: "↦", ell: "ℓ", hbar: "ℏ",
};

/** Commands that only affect layout. Their names are noise in a label. */
const STRUCTURAL = new Set([
  "frac", "left", "right", "big", "Big", "bigg", "Bigg", "begin", "end",
  "text", "mathrm", "mathbf", "mathcal", "mathbb", "operatorname", "displaystyle",
  "vec", "hat", "bar", "tilde", "dot", "overline", "underline", "quad", "qquad",
]);

/** A short, readable label for the outline.
 *
 *  Stripping LaTeX wholesale leaves orphaned subscript markers - "\\mu_i" became
 *  "_i" - while keeping command names turns "\\nabla\\Phi" into "nablaPhi".
 *  Symbols are substituted, layout commands dropped, and braces removed.
 */
export function outlineLabel(block: Block): string {
  const source = block.content || block.items[0] || "";
  return source
    .replace(/\\(?:begin|end)\{[^}]*\}/g, " ")
    .replace(/\\([a-zA-Z]+)/g, (_, name: string) =>
      SYMBOLS[name] ?? (STRUCTURAL.has(name) ? " " : name),
    )
    .replace(/\\\\|&/g, " ")
    .replace(/[{}$]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 44);
}

export function toMarkdown(note: Note): string {
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
