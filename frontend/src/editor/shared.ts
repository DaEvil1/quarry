// Names shared by two entries, in the editor (docs/SPEC.md §14.10): the document's choice lines (`%% Isolde: Isolde
// Marr`), kept in step with the text, and the shared names settled by the nearest one above them. Choice lines are
// found again only when a change touches a margin-note line (or the names change); any other keystroke just moves
// them, so the typing budget holds.

import { Facet, StateEffect, StateField, type EditorState, type Transaction } from "@codemirror/state";

import type { Choice, Hit, Matcher } from "../world/matcher";

/** Tell the editor the world's names changed (a new entry, another spelling, a different setting). */
export const namesChanged = StateEffect.define<null>();

/** The matcher the editor reads names with. */
export const matcherFacet = Facet.define<() => Matcher, (() => Matcher) | null>({ combine: (v) => v[0] ?? null });

const MARGIN = "%%";

/** Did a change touch a line that is (or was) a margin note? */
function touchesMargin(tr: Transaction): boolean {
  let touched = false;
  tr.changes.iterChangedRanges((fromA, toA, fromB, toB) => {
    if (touched) return;
    const a = tr.startState.doc;
    const b = tr.state.doc;
    touched = a.sliceString(a.lineAt(fromA).from, a.lineAt(toA).to).includes(MARGIN)
      || b.sliceString(b.lineAt(fromB).from, b.lineAt(toB).to).includes(MARGIN);
  });
  return touched;
}

const find = (state: EditorState): Choice[] => {
  const m = state.facet(matcherFacet)?.();
  return m && !m.empty ? m.choices(state.doc.toString()) : [];
};

export const choicesField = StateField.define<Choice[]>({
  create: find,
  update(choices, tr) {
    if (tr.effects.some((e) => e.is(namesChanged))) return find(tr.state);
    if (!tr.docChanged) return choices;
    if (touchesMargin(tr)) return find(tr.state);
    if (!choices.length) return choices;
    return choices.map((c) => ({ ...c, start: tr.changes.mapPos(c.start), end: tr.changes.mapPos(c.end) }));
  },
});

export const choicesOf = (state: EditorState): Choice[] => state.field(choicesField, false) ?? [];

/** The choice line that starts at a line's start, if that line is one. */
export function choiceOn(state: EditorState, lineFrom: number): Choice | undefined {
  return choicesOf(state).find((c) => c.start === lineFrom);
}

/** Hits of a line, their shared names settled by the choice lines above them. */
export function settle(state: EditorState, matcher: Matcher, hits: Hit[]): Hit[] {
  const choices = choicesOf(state);
  return choices.length ? matcher.resolve(hits, choices) : hits;
}

/** The text of a choice line: who a shared name means from here (null: nobody in particular, `?`). */
export function choiceText(form: string, names: string[] | null): string {
  return `%% ${form}: ${names ? names.join(", ") : "?"}`;
}

/** The changes that make a shared name mean `names` from the line `lineFrom` on: a new choice line above it, or the
 * one right above rewritten when it is already a choice for this name. */
export function chooseChange(state: EditorState, lineFrom: number, key: string, form: string, names: string[] | null) {
  const text = choiceText(form, names);
  const line = state.doc.lineAt(lineFrom);
  if (line.number > 1) {
    const above = state.doc.line(line.number - 1);
    const c = choiceOn(state, above.from);
    if (c && c.key === key) return { from: above.from, to: above.to, insert: text };
  }
  return { from: line.from, insert: `${text}\n` };
}
