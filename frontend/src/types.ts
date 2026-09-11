// Mirrors lectura.schema. The canonical note is the contract between the
// pipeline and everything that displays or edits it.

export type Origin = "extracted" | "supplement" | "user";

export type BlockType =
  | "heading"
  | "text"
  | "equation"
  | "bullet_list"
  | "numbered_list"
  | "definition"
  | "table"
  | "diagram"
  | "code";

export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Block {
  id: string;
  type: BlockType;
  content: string;
  items: string[];
  level: number | null;
  origin: Origin;
  confidence: number | null;
  bbox: BBox | null;
  source_image: string | null;
  flags: string[];
}

export interface Note {
  schema_version: string;
  id: string;
  title: string | null;
  created_at: string;
  source_images: string[];
  blocks: Block[];
}

export interface ExtractResponse {
  note: Note;
  seconds: number;
  backend: string;
  preprocess: string;
  /** Data URL of the corrected image the model read. The upload itself is
   *  often HEIC, which browsers cannot display. */
  preview: string;
}

export const THEMES = ["academic", "dark", "minimal", "notebook"] as const;
export type Theme = (typeof THEMES)[number];

export const CONFIDENCE_THRESHOLD = 0.75;

/** Blocks the editor should surface first: flagged, or low confidence.
 *
 *  Deliberately single-argument. An optional threshold parameter here silently
 *  absorbed the index when passed to Array.filter, so every block after the
 *  first compared its confidence against its own position and the interface
 *  reported 12 of 13 blocks as doubtful when none were. */
export function isUncertain(block: Block): boolean {
  if (block.flags.length > 0) return true;
  return block.confidence !== null && block.confidence < CONFIDENCE_THRESHOLD;
}

export const LIST_TYPES: BlockType[] = ["bullet_list", "numbered_list"];
