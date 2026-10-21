// The prose editor: CodeMirror 6 set up for writing rather than code. Markdown, soft wrap in a centred column of
// about 70 characters, the app's colours (so it follows light and dark), focus mode, typewriter scrolling, and
// names from the bible underlined: dotted for mentions, wavy for likely misspellings.

import { history, defaultKeymap, historyKeymap } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { highlightSelectionMatches, search, searchKeymap } from "@codemirror/search";
import { Compartment, EditorState, RangeSetBuilder, StateEffect, StateField, type Extension } from "@codemirror/state";
import {
  Decoration,
  EditorView,
  ViewPlugin,
  drawSelection,
  keymap,
  placeholder,
  type DecorationSet,
  type ViewUpdate,
} from "@codemirror/view";
import { tags as t } from "@lezer/highlight";

import type { Mention } from "../types";

// ---- names: mention marks, kept in place as the text changes, replaced after each save -----------------------

export const setMentions = StateEffect.define<Mention[]>();

function mentionDecorations(doc: { length: number }, mentions: Mention[]): DecorationSet {
  const b = new RangeSetBuilder<Decoration>();
  for (const m of [...mentions].sort((a, z) => a.start - z.start)) {
    if (m.end > doc.length || m.start >= m.end) continue;
    b.add(
      m.start,
      m.end,
      Decoration.mark({
        class: m.kind === "near_miss" ? "cm-near-miss" : "cm-mention",
        attributes: { "data-entity": m.entity_id, "data-name": m.entity_name, "data-kind": m.kind, "data-word": m.matched_text },
      }),
    );
  }
  return b.finish();
}

const mentionField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(deco, tr) {
    let next = deco.map(tr.changes);
    for (const e of tr.effects) if (e.is(setMentions)) next = mentionDecorations(tr.state.doc, e.value);
    return next;
  },
  provide: (f) => EditorView.decorations.from(f),
});

// ---- focus mode: everything but the paragraph you're in is dimmed -------------------------------------------

const dimLine = Decoration.line({ class: "cm-dim" });

function paragraphAround(view: EditorView): [number, number] {
  const doc = view.state.doc;
  const here = doc.lineAt(view.state.selection.main.head).number;
  let from = here;
  let to = here;
  while (from > 1 && doc.line(from - 1).text.trim() !== "") from--;
  while (to < doc.lines && doc.line(to + 1).text.trim() !== "") to++;
  return [from, to];
}

const focusPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = this.build(view);
    }
    update(u: ViewUpdate) {
      if (u.docChanged || u.selectionSet || u.viewportChanged) this.decorations = this.build(u.view);
    }
    build(view: EditorView): DecorationSet {
      const [from, to] = paragraphAround(view);
      const b = new RangeSetBuilder<Decoration>();
      for (const { from: vf, to: vt } of view.visibleRanges) {
        for (let pos = vf; pos <= vt; ) {
          const line = view.state.doc.lineAt(pos);
          if (line.number < from || line.number > to) b.add(line.from, line.from, dimLine);
          pos = line.to + 1;
        }
      }
      return b.finish();
    }
  },
  { decorations: (v) => v.decorations },
);

// ---- typewriter: the line being written stays in the middle of the screen ----------------------------------

const typewriter = EditorView.updateListener.of((u) => {
  if (!(u.docChanged || u.selectionSet) || !u.view.hasFocus) return;
  const head = u.state.selection.main.head;
  // not inside the update itself: CodeMirror refuses nested dispatches
  queueMicrotask(() => u.view.dispatch({ effects: EditorView.scrollIntoView(head, { y: "center" }) }));
});

// ---- look ---------------------------------------------------------------------------------------------------

const theme = EditorView.theme({
  "&": { color: "var(--text)", backgroundColor: "transparent", fontSize: "var(--prose-size, 18px)", height: "100%" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--prose)", lineHeight: "1.7", overflow: "auto" },
  ".cm-content": { maxWidth: "70ch", margin: "0 auto", padding: "28px 4px 45vh", caretColor: "var(--accent)" },
  ".cm-line": { padding: "0" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, ::selection": {
    backgroundColor: "color-mix(in srgb, var(--accent) 28%, transparent) !important",
  },
  ".cm-placeholder": { color: "var(--muted)", fontStyle: "italic" },
  ".cm-dim": { opacity: "0.32", transition: "opacity .15s" },
  ".cm-mention": { textDecoration: "underline dotted color-mix(in srgb, var(--accent) 55%, transparent)", textUnderlineOffset: "4px" },
  ".cm-near-miss": { textDecoration: "underline wavy var(--warn)", textDecorationSkipInk: "none", textUnderlineOffset: "4px", cursor: "pointer" },
  ".cm-searchMatch": { backgroundColor: "var(--warn-soft)", outline: "1px solid var(--warn)" },
  ".cm-searchMatch.cm-searchMatch-selected": { backgroundColor: "var(--accent-soft)" },
  ".cm-panels": { backgroundColor: "var(--surface)", color: "var(--text)", fontFamily: "system-ui, sans-serif", fontSize: "13px" },
  ".cm-panels.cm-panels-top": { borderBottom: "1px solid var(--border)" },
  ".cm-panel.cm-search input, .cm-panel.cm-search button": { font: "inherit" },
  ".cm-textfield": { backgroundColor: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: "4px" },
  ".cm-button": { backgroundImage: "none", backgroundColor: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: "4px" },
});

const highlight = HighlightStyle.define([
  { tag: t.heading1, fontSize: "1.45em", fontWeight: "700" },
  { tag: t.heading2, fontSize: "1.25em", fontWeight: "700" },
  { tag: [t.heading3, t.heading4, t.heading5, t.heading6], fontWeight: "700" },
  { tag: t.emphasis, fontStyle: "italic" },
  { tag: t.strong, fontWeight: "700" },
  { tag: t.strikethrough, textDecoration: "line-through" },
  { tag: t.quote, color: "var(--muted)", fontStyle: "italic" },
  { tag: [t.link, t.url], color: "var(--accent)" },
  { tag: t.monospace, fontFamily: "var(--mono)", fontSize: "0.85em" },
  { tag: [t.processingInstruction, t.meta, t.contentSeparator], color: "var(--muted)" },
]);

// ---- the editor ---------------------------------------------------------------------------------------------

export interface ProseOptions {
  doc: string;
  onChange: (text: string) => void;
  onSave: () => void;
  onNearMiss?: (info: { word: string; entityId: string; name: string; from: number; to: number; x: number; y: number }) => void;
  placeholderText?: string;
  readOnly?: boolean;
}

export interface Prose {
  view: EditorView;
  setFocusMode(on: boolean): void;
  setTypewriter(on: boolean): void;
  setMentions(mentions: Mention[]): void;
  replaceDoc(text: string): void;
  replaceRange(from: number, to: number, text: string): void;
  destroy(): void;
}

export function createProse(parent: HTMLElement, opts: ProseOptions): Prose {
  const focusMode = new Compartment();
  const typewriterMode = new Compartment();
  const extensions: Extension[] = [
    history(),
    drawSelection(),
    search({ top: true }),
    highlightSelectionMatches(),
    markdown(),
    syntaxHighlighting(highlight),
    EditorView.lineWrapping,
    EditorState.allowMultipleSelections.of(false),
    EditorState.readOnly.of(!!opts.readOnly),
    EditorView.editable.of(!opts.readOnly),
    theme,
    mentionField,
    focusMode.of([]),
    typewriterMode.of([]),
    placeholder(opts.placeholderText ?? "Write…"),
    keymap.of([
      { key: "Mod-s", preventDefault: true, run: () => (opts.onSave(), true) },
      ...searchKeymap,
      ...historyKeymap,
      ...defaultKeymap,
    ]),
    EditorView.contentAttributes.of({ spellcheck: "true", autocapitalize: "sentences", "aria-label": "Chapter text" }),
    EditorView.updateListener.of((u) => {
      if (u.docChanged) opts.onChange(u.state.doc.toString());
    }),
    EditorView.domEventHandlers({
      click(e, view) {
        const el = (e.target as HTMLElement).closest(".cm-near-miss") as HTMLElement | null;
        if (!el || !opts.onNearMiss) return false;
        const pos = view.posAtDOM(el);
        const word = el.dataset.word ?? el.textContent ?? "";
        const rect = el.getBoundingClientRect();
        opts.onNearMiss({ word, entityId: el.dataset.entity ?? "", name: el.dataset.name ?? "", from: pos,
                          to: pos + (el.textContent ?? "").length, x: rect.left, y: rect.bottom });
        return true;
      },
    }),
  ];
  const view = new EditorView({ parent, state: EditorState.create({ doc: opts.doc, extensions }) });
  return {
    view,
    setFocusMode: (on) => view.dispatch({ effects: focusMode.reconfigure(on ? focusPlugin : []) }),
    setTypewriter: (on) => view.dispatch({ effects: typewriterMode.reconfigure(on ? typewriter : []) }),
    setMentions: (m) => view.dispatch({ effects: setMentions.of(m) }),
    replaceDoc(text) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
    },
    replaceRange(from, to, text) {
      view.dispatch({ changes: { from, to, insert: text } });
    },
    destroy: () => view.destroy(),
  };
}

export { countWords } from "../words";
