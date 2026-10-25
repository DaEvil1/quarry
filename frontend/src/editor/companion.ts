// The writing companion in the editor (docs/WORLD-MODEL.md §5, §7): margin notes shown as notes, the companion's
// marks while Revising, the quick-fix strip from the keyboard (Alt+Enter), a classifying pass (F8), stashing a
// thought (Ctrl+Shift+S), and noticing a scene break. Nothing here opens while typing.

import { type ChangeDesc, RangeSetBuilder, StateEffect, StateField, type EditorState, type Extension } from "@codemirror/state";
import { Decoration, EditorView, ViewPlugin, keymap, showTooltip, type DecorationSet, type Tooltip, type ViewUpdate } from "@codemirror/view";

import type { Finding } from "../world/findings";
import { findingStripDom, type FindingActions } from "./strips";
import { choiceOn, namesChanged } from "./shared";

/** A finding where it is now in the text (its analysis was of an older version). */
export interface Marked {
  from: number;
  to: number;
  finding: Finding;
}

export interface CompanionHooks {
  /** Drafting (false) or Revising (true) */
  revising(): boolean;
  /** the latest findings that have a place in the text, mapped to the text as it is now */
  marked(): Marked[];
  /** which of them to draw (Revising, with that editor's marks switched on) */
  drawn(f: Finding): boolean;
  findingActions(m: Marked, view: EditorView): FindingActions;
  /** what a name, misspelling or selection at a position shows (the same as resting on it), if anything */
  stripAt(view: EditorView, pos: number): { from: number; dom: HTMLElement } | null;
  /** the next likely misspelling after a position (for F8) */
  nextMiss(state: EditorState, after: number): { from: number; to: number } | null;
  stash(): void;
  sceneBreak(): void;
  /** a journal entry: a %% line is ordinary text, and only choice lines are notes (docs/SPEC.md §14.10) */
  choicesOnly?: boolean;
}

// ---- margin notes: a line starting with %% is a note to yourself ------------------------------------------------

const marginLine = Decoration.line({ class: "cm-margin", attributes: { spellcheck: "false" } });
const MARGIN = /^[ \t]*%%/;

/** Margin notes dimmed: every %% line in a chapter; in a journal entry only choice lines. */
const marginPlugin = (choicesOnly: boolean) => ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = this.build(view);
    }
    update(u: ViewUpdate) {
      if (u.docChanged || u.viewportChanged || (choicesOnly && u.transactions.some((tr) => tr.effects.some((e) => e.is(namesChanged))))) {
        this.decorations = this.build(u.view);
      }
    }
    build(view: EditorView): DecorationSet {
      const b = new RangeSetBuilder<Decoration>();
      let next = 0;
      for (const { from, to } of view.visibleRanges) {
        for (let pos = Math.max(from, next); pos <= to; ) {
          const line = view.state.doc.lineAt(pos);
          if (choicesOnly ? choiceOn(view.state, line.from) : MARGIN.test(line.text)) b.add(line.from, line.from, marginLine);
          next = pos = line.to + 1;
        }
      }
      return b.finish();
    }
  },
  { decorations: (v) => v.decorations },
);

// ---- the companion's marks (Revising) -------------------------------------------------------------------------

export const marksChanged = StateEffect.define<DecorationSet>();

export const marksField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(marks, tr) {
    for (const e of tr.effects) if (e.is(marksChanged)) return e.value;
    return tr.docChanged ? marks.map(tr.changes) : marks;
  },
  provide: (f) => EditorView.decorations.from(f),
});

const markClass: Record<string, string> = {
  new_name: "cm-find cm-find-name",
  other_name: "cm-find cm-find-name",
};

export function buildMarks(state: EditorState, hooks: CompanionHooks): DecorationSet {
  const b = new RangeSetBuilder<Decoration>();
  if (!hooks.revising()) return b.finish();
  const list = hooks
    .marked()
    .filter((m) => hooks.drawn(m.finding) && m.from < m.to && m.to <= state.doc.length)
    .sort((x, y) => x.from - y.from || x.to - y.to);
  let last = -1;
  for (const m of list) {
    if (m.from < last) continue;
    b.add(m.from, m.to, Decoration.mark({ class: markClass[m.finding.rule] ?? "cm-find", attributes: { "data-finding": m.finding.rule } }));
    last = m.to;
  }
  return b.finish();
}

/** The finding marked at a position, if any. */
export function markedAt(hooks: CompanionHooks, pos: number): Marked | undefined {
  return hooks.marked().find((m) => m.from <= pos && pos <= m.to);
}

// ---- the strip from the keyboard: Alt+Enter, F8 ---------------------------------------------------------------

/** Open (or close) the strip from the keyboard; it takes the place of the strip a selection would show. */
export const openKbd = StateEffect.define<Tooltip | null>();

const kbdField = StateField.define<Tooltip | null>({
  create: () => null,
  update(tip, tr) {
    for (const e of tr.effects) if (e.is(openKbd)) return e.value;
    return tr.docChanged ? null : tip;
  },
  provide: (f) => showTooltip.from(f),
});

/** Keyboard in the strip: arrows move between its buttons, Escape goes back to the text; a button that finishes its
 * job closes the strip and returns to the text too. */
function keyboardStrip(view: EditorView, inner: HTMLElement): HTMLElement {
  const box = document.createElement("div");
  box.className = "kbd-strip";
  box.append(inner);
  const focusables = () => [...box.querySelectorAll<HTMLElement>("button:not([disabled]), input")];
  const close = () => {
    view.dispatch({ effects: openKbd.of(null) });
    view.focus();
  };
  box.addEventListener("keydown", (e) => {
    const xs = focusables();
    const i = xs.indexOf(document.activeElement as HTMLElement);
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if ((e.key === "ArrowRight" || e.key === "ArrowDown") && !(document.activeElement instanceof HTMLInputElement)) {
      e.preventDefault();
      xs[(i + 1) % xs.length]?.focus();
    } else if ((e.key === "ArrowLeft" || e.key === "ArrowUp") && !(document.activeElement instanceof HTMLInputElement)) {
      e.preventDefault();
      xs[(i - 1 + xs.length) % xs.length]?.focus();
    }
  });
  box.addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest("button");
    // a fix that changed the text has closed the strip already: back to the text. A button that opened a next step
    // (a list, an input) is gone by now; one that did its job is still there, so close the strip.
    setTimeout(() => {
      if (!box.isConnected) view.focus();
      else if (b && b.isConnected) close();
    });
  });
  requestAnimationFrame(() => focusables()[0]?.focus());
  return box;
}

function openStripAt(view: EditorView, hooks: CompanionHooks, pos: number): boolean {
  const strip = hooks.stripAt(view, pos);
  if (strip) {
    view.dispatch({ effects: openKbd.of({ pos: strip.from, above: false, strictSide: false, create: (v) => ({ dom: keyboardStrip(v, strip.dom) }) }) });
    return true;
  }
  const m = markedAt(hooks, pos);
  if (m) {
    view.dispatch({
      effects: openKbd.of({
        pos: m.from,
        above: false,
        strictSide: false,
        create: (v) => ({ dom: keyboardStrip(v, findingStripDom(m.finding.message, hooks.findingActions(m, v))) }),
      }),
    });
    return true;
  }
  return false;
}

/** F8: the next likely misspelling or possible new name after the cursor (round to the top), selected, its strip open. */
function sweep(view: EditorView, hooks: CompanionHooks): boolean {
  const head = view.state.selection.main.to;
  const candidates: { from: number; to: number }[] = hooks
    .marked()
    .filter((m) => m.finding.rule === "new_name" || m.finding.rule === "near_miss" || m.finding.rule === "other_name")
    .map(({ from, to }) => ({ from, to }));
  const miss = hooks.nextMiss(view.state, head) ?? hooks.nextMiss(view.state, -1);
  if (miss) candidates.push(miss);
  const after = candidates.filter((c) => c.from >= head).sort((a, b) => a.from - b.from)[0];
  const next = after ?? candidates.sort((a, b) => a.from - b.from)[0];
  if (!next) return true;
  view.dispatch({ selection: { anchor: next.from, head: next.to }, effects: EditorView.scrollIntoView(next.from, { y: "center" }) });
  openStripAt(view, hooks, next.from);
  return true;
}

// ---- scene breaks: a line of *** (a natural break for Drafting) ----------------------------------------------

const SCENE_BREAK = /^\s*\*\s*\*\s*\*\s*$/;

function sceneBreaks(hooks: CompanionHooks) {
  return EditorView.updateListener.of((u) => {
    if (!u.docChanged || !u.transactions.some((tr) => tr.isUserEvent("input"))) return;
    let newline = false;
    u.changes.iterChanges((_fa, _ta, _fb, _tb, ins) => (newline ||= ins.toString().includes("\n")));
    if (!newline) return;
    const line = u.state.doc.lineAt(u.state.selection.main.head);
    if (line.number > 1 && SCENE_BREAK.test(u.state.doc.line(line.number - 1).text)) hooks.sceneBreak();
  });
}

export function companionExtensions(hooks: CompanionHooks): Extension[] {
  return [
    marginPlugin(!!hooks.choicesOnly),
    marksField,
    kbdField,
    sceneBreaks(hooks),
    keymap.of([
      { key: "Alt-Enter", preventDefault: true, run: (v) => (openStripAt(v, hooks, v.state.selection.main.head) || openStripAt(v, hooks, v.state.selection.main.head - 1), true) },
      { key: "F8", preventDefault: true, run: (v) => sweep(v, hooks) },
      { key: "Mod-Shift-s", preventDefault: true, run: () => (hooks.stash(), true) },
    ]),
  ];
}

/** Map positions from an older version of the text to now: changes are added as they happen. */
export class Since {
  private desc: ChangeDesc | null = null;
  add(changes: ChangeDesc) {
    this.desc = this.desc ? this.desc.composeDesc(changes) : changes;
  }
  map(pos: number, assoc = 1): number {
    return this.desc ? this.desc.mapPos(pos, assoc) : pos;
  }
}
