// Changes since a checkpoint (docs/SPEC.md §11.6): while Revising, what changed since a labelled checkpoint is tinted,
// the lines it is on get a bar in the margin, and removed text leaves a small mark that shows what was there when
// the pointer rests on it. Worked out when typing pauses, paragraph by paragraph first and then word by word inside
// the paragraphs that changed, so it stays within the typing budget; between two workings-out the marks just move
// with the text. Separate from the name colours and the companion's marks.

import { diffArrays, diffWordsWithSpace } from "diff";
import { StateEffect, StateField, type EditorState } from "@codemirror/state";
import { Decoration, EditorView, WidgetType, type DecorationSet } from "@codemirror/view";

/** One change, placed in the text as it is now: `from`–`to` is new or changed text (empty for a pure removal), and
 * `was` what stood there at the checkpoint. */
export interface Change {
  from: number;
  to: number;
  was: string;
}

export interface Changes {
  changes: Change[];
  /** words added or changed */
  words: number;
  /** passages removed with nothing in their place */
  removed: number;
}

const WORD = /[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu;
const countWords = (s: string) => s.match(WORD)?.length ?? 0;
/** past this size a changed block is marked as a whole rather than word by word */
const WORDWISE_LIMIT = 20_000;

/** Word-level changes inside one block that changed (`at` is where `now` starts in the whole text). */
function inside(was: string, now: string, at: number, out: Change[]): void {
  if (!was || !now || was.length > WORDWISE_LIMIT || now.length > WORDWISE_LIMIT) {
    out.push({ from: at, to: at + now.length, was });
    return;
  }
  let pos = at;
  let pending: string | null = null;
  for (const part of diffWordsWithSpace(was, now)) {
    if (part.removed) {
      pending = (pending ?? "") + part.value;
    } else if (part.added) {
      out.push({ from: pos, to: pos + part.value.length, was: pending ?? "" });
      pending = null;
      pos += part.value.length;
    } else {
      if (pending !== null) out.push({ from: pos, to: pos, was: pending });
      pending = null;
      pos += part.value.length;
    }
  }
  if (pending !== null) out.push({ from: pos, to: pos, was: pending });
}

/** What changed from `base` (the checkpoint) to `now`, placed in `now`. */
export function changesSince(base: string, now: string): Changes {
  const out: Change[] = [];
  const parts = diffArrays(base.split("\n"), now.split("\n"));
  let pos = 0;
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]!;
    const len = (lines: string[]) => lines.reduce((n, l) => n + l.length + 1, 0);
    if (!part.added && !part.removed) {
      pos += len(part.value);
      continue;
    }
    if (part.removed) {
      const next = parts[i + 1];
      const was = part.value.join("\n");
      if (next?.added) {
        // a changed block: word by word inside it
        const now = next.value.join("\n");
        inside(was, now, pos, out);
        pos += len(next.value);
        i++;
      } else {
        out.push({ from: pos, to: pos, was });
      }
      continue;
    }
    // added lines
    // the paragraph, not the blank line after it
    const text = part.value.join("\n").replace(/\s+$/, "");
    out.push({ from: pos, to: pos + text.length, was: "" });
    pos += len(part.value);
  }
  // a removal and an addition of nothing but spacing are no change worth marking
  const changes = out.filter((c) => (c.to > c.from ? now.slice(c.from, c.to).trim() || c.was.trim() : c.was.trim()));
  return {
    changes,
    words: changes.reduce((n, c) => n + countWords(now.slice(c.from, c.to)), 0),
    removed: changes.filter((c) => c.from === c.to).length,
  };
}

/** "312 words changed, 4 passages removed since “before the polish”" */
export function changesLine(c: Changes, label: string): string {
  const words = `${c.words.toLocaleString()} ${c.words === 1 ? "word" : "words"} changed`;
  const removed = `${c.removed} ${c.removed === 1 ? "passage" : "passages"} removed`;
  return `${words}, ${removed} since “${label}”`;
}

// ---- in the editor ------------------------------------------------------------------------------------------------

class RemovedMark extends WidgetType {
  constructor(readonly was: string) {
    super();
  }
  eq(other: RemovedMark) {
    return other.was === this.was;
  }
  toDOM() {
    const el = document.createElement("span");
    el.className = "cm-removed";
    el.setAttribute("aria-label", "Removed text");
    el.dataset.testid = "removed-mark";
    return el;
  }
  ignoreEvent() {
    return false;
  }
}

const tint = Decoration.mark({ class: "cm-changed", attributes: { "data-testid": "changed" } });
const bar = Decoration.line({ class: "cm-changed-line" });

/** Set the changes to show (null: none). */
export const setChanges = StateEffect.define<Change[] | null>();

interface Shown {
  changes: Change[];
  decorations: DecorationSet;
}

function build(state: EditorState, changes: Change[]): DecorationSet {
  const doc = state.doc;
  const lineStarts = new Set<number>();
  for (const c of changes) {
    if (c.from > doc.length || c.to > doc.length) continue;
    const first = doc.lineAt(c.from).number;
    const last = doc.lineAt(c.to).number;
    for (let n = first; n <= last; n++) lineStarts.add(doc.line(n).from);
  }
  const ranges = [...lineStarts].map((at) => bar.range(at));
  for (const c of changes) {
    if (c.to > doc.length) continue;
    ranges.push(c.from === c.to ? Decoration.widget({ widget: new RemovedMark(c.was), side: 1 }).range(c.from) : tint.range(c.from, c.to));
  }
  return Decoration.set(ranges, true);
}

export const changesField = StateField.define<Shown>({
  create: () => ({ changes: [], decorations: Decoration.none }),
  update(shown, tr) {
    for (const e of tr.effects) {
      if (e.is(setChanges)) return { changes: e.value ?? [], decorations: e.value ? build(tr.state, e.value) : Decoration.none };
    }
    if (!tr.docChanged || !shown.changes.length) return shown;
    const changes = shown.changes.map((c) => ({ ...c, from: tr.changes.mapPos(c.from, 1), to: tr.changes.mapPos(c.to, -1) }));
    return { changes: changes.map((c) => (c.to < c.from ? { ...c, to: c.from } : c)), decorations: shown.decorations.map(tr.changes) };
  },
  provide: (f) => EditorView.decorations.from(f, (s) => s.decorations),
});

/** The change at a position that replaced or removed something, for "what was there". */
export function changeAt(state: EditorState, pos: number): Change | undefined {
  return state.field(changesField, false)?.changes.find((c) => c.was.trim() && c.from <= pos && pos <= c.to);
}
