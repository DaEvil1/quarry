// The prose editor: CodeMirror 6 set up for writing rather than code. Markdown, soft wrap in a centred column, the
// app's colours (so it follows light and dark), focus mode, typewriter scrolling, and the world's names coloured by
// kind as they are typed, with cards and quick fixes one gesture away (docs/WORLD-MODEL.md §5).
//
// The rule: nothing opens because of a keystroke. Colours and underlines update while typing; a card or a strip
// opens only when the pointer rests on a word (after a quiet moment since the last key) or text is selected.

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
  hoverTooltip,
  keymap,
  placeholder,
  showTooltip,
  type DecorationSet,
  type Tooltip,
  type ViewUpdate,
} from "@codemirror/view";
import { tags as t } from "@lezer/highlight";

import type { WritingPrefs } from "../prefs";
import type { EntityKind, EntityRef } from "../types";
import type { Card } from "../world/cards";
import type { Hit, Matcher } from "../world/matcher";
import { cardDom, selectionStripDom, nearMissStripDom } from "./strips";

export { countWords } from "../words";

/** What the editor needs from the app to show the world. */
export interface WorldHooks {
  matcher(): Matcher;
  card(id: string): Card | undefined;
  names(): EntityRef[];
  prefs(): WritingPrefs;
  open(entityId: string): void;
  /** "another spelling" for a misspelling, or for a selection: add `word` as another name of the entry */
  addName(entityId: string, word: string): Promise<void>;
  notATypo(word: string): Promise<void>;
  /** a selection or new word becomes a bible entry */
  create(name: string, kind: EntityKind): Promise<void>;
  /** "not a name here": the phrase around a wrongly matched name */
  exclude(entityId: string, phrase: string): Promise<void>;
}

// ---- names: coloured by kind, recomputed for what is on screen --------------------------------------------------

/** Tell the editor the world's names changed (a new entry, another spelling, a different setting). */
export const namesChanged = StateEffect.define<null>();

function namesPlugin(hooks: WorldHooks) {
  return ViewPlugin.fromClass(
    class {
      decorations: DecorationSet;
      constructor(view: EditorView) {
        this.decorations = this.build(view);
      }
      update(u: ViewUpdate) {
        if (u.docChanged || u.viewportChanged || u.transactions.some((tr) => tr.effects.some((e) => e.is(namesChanged)))) {
          this.decorations = this.build(u.view);
        }
      }
      build(view: EditorView): DecorationSet {
        const prefs = hooks.prefs();
        const matcher = hooks.matcher();
        const b = new RangeSetBuilder<Decoration>();
        if (matcher.empty) return b.finish();
        let last = -1;
        for (const { from, to } of view.visibleRanges) {
          // whole lines, so a name is never cut in half at the edge of the screen
          const start = Math.max(view.state.doc.lineAt(from).from, last);
          const end = view.state.doc.lineAt(to).to;
          if (start >= end) continue;
          for (const h of matcher.scan(view.state.doc.sliceString(start, end), start, prefs.underlines)) {
            if (h.start < last) continue;
            b.add(h.start, h.end, markFor(h, prefs));
            last = h.end;
          }
          last = Math.max(last, end);
        }
        return b.finish();
      }
    },
    { decorations: (v) => v.decorations },
  );
}

const markCache = new Map<string, Decoration>();
function markFor(h: Hit, prefs: WritingPrefs): Decoration {
  const coloured = prefs.colourNames && !prefs.plainKinds.includes(h.entityKind as EntityKind);
  const cls = h.kind === "near_miss" ? "cm-near-miss" : `cm-name${coloured ? ` cm-k-${h.entityKind}` : ""}`;
  const key = `${cls}|${h.entityId}|${h.kind}`;
  let d = markCache.get(key);
  if (!d) {
    // spellcheck off: invented names are not typos
    d = Decoration.mark({ class: cls, attributes: { spellcheck: "false", "data-entity": h.entityId, "data-hit": h.kind } });
    markCache.set(key, d);
  }
  return d;
}

/** The name (or likely misspelling) under a position, found the same way the colours were. */
function hitAt(view: EditorView, hooks: WorldHooks, pos: number): Hit | undefined {
  const line = view.state.doc.lineAt(pos);
  return hooks
    .matcher()
    .scan(line.text, line.from, hooks.prefs().underlines)
    .find((h) => h.start <= pos && pos < h.end);
}

/** The few words around a match, for "not a name here" ("rose garden"). */
function phraseAround(view: EditorView, h: Hit): string {
  const line = view.state.doc.lineAt(h.start);
  const after = line.text.slice(h.end - line.from).match(/^\s+([\p{L}'’-]+)/u)?.[1];
  if (after) return `${h.matched} ${after}`;
  const before = line.text.slice(0, h.start - line.from).match(/([\p{L}'’-]+)\s+$/u)?.[1];
  return before ? `${before} ${h.matched}` : h.matched;
}

// ---- intent: the hover card / strip, and the selection strip ------------------------------------------------------

// whether Ctrl/Cmd is held (for "cards only with Ctrl"), tracked once for the whole page
let ctrl = false;
if (typeof window !== "undefined") {
  const track = (e: KeyboardEvent) => {
    ctrl = e.ctrlKey || e.metaKey;
  };
  window.addEventListener("keydown", track);
  window.addEventListener("keyup", track);
  window.addEventListener("blur", () => (ctrl = false));
}
let lastKey = 0;

function intent(hooks: WorldHooks): Extension[] {

  const hover = hoverTooltip(
    (view, pos) => {
      const prefs = hooks.prefs();
      if (Date.now() - lastKey < prefs.quietMs) return null;
      if (prefs.cardsWithCtrl && !ctrl) return null;
      const h = hitAt(view, hooks, pos);
      if (!h) return null;
      return {
        pos: h.start,
        end: h.end,
        above: false,
        create: (v): { dom: HTMLElement } => {
          if (h.kind === "near_miss") {
            const target = hooks.card(h.entityId);
            return {
              dom: nearMissStripDom(h.matched, target?.name ?? "?", {
                replace: () => v.dispatch({ changes: { from: h.start, to: h.end, insert: target?.name ?? h.matched } }),
                spelling: () => hooks.addName(h.entityId, h.matched),
                ignore: () => hooks.notATypo(h.matched),
              }),
            };
          }
          return {
            dom: cardDom(hooks.card(h.entityId), {
              open: () => hooks.open(h.entityId),
              notHere: () => hooks.exclude(h.entityId, phraseAround(v, h)),
            }),
          };
        },
      };
    },
    { hoverTime: hooks.prefs().cardDelay, hideOnChange: true },
  );

  // selecting words is intent too: offer to make them an entry, or another name of one
  const selectionTip = StateField.define<readonly Tooltip[]>({
    create: () => [],
    update(tips, tr) {
      if (!tr.selection && !tr.docChanged) return tips;
      if (tr.docChanged) return [];
      const sel = tr.state.selection.main;
      if (sel.empty || tr.state.readOnly) return [];
      const text = tr.state.sliceDoc(sel.from, sel.to).trim();
      if (text.length < 2 || text.length > 80 || text.includes("\n")) return [];
      return [
        {
          pos: sel.to,
          above: false,
          strictSide: false,
          create: (view) => ({
            dom: selectionStripDom(text, hooks.names(), {
              create: async (kind) => {
                await hooks.create(text, kind);
                view.dispatch({ selection: { anchor: sel.to } });
              },
              addName: async (id) => {
                await hooks.addName(id, text);
                view.dispatch({ selection: { anchor: sel.to } });
              },
              done: () => view.focus(),
            }),
          }),
        },
      ];
    },
    provide: (f) => showTooltip.computeN([f], (state) => state.field(f)),
  });

  return [
    hover,
    selectionTip,
    EditorView.domEventHandlers({
      keydown: () => {
        lastKey = Date.now();
        return false;
      },
    }),
  ];
}

// ---- focus mode: everything but the paragraph you're in is dimmed ---------------------------------------------

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

// ---- typewriter: while typing, the line being written stays in the middle of the screen -------------------------
// (only while typing: recentring on a click or a selection makes the page jump, a common complaint)

const typewriter = EditorView.updateListener.of((u) => {
  if (!u.docChanged || !u.view.hasFocus) return;
  if (!u.transactions.some((tr) => tr.isUserEvent("input") || tr.isUserEvent("delete"))) return;
  const head = u.state.selection.main.head;
  // not inside the update itself: CodeMirror refuses nested dispatches
  queueMicrotask(() => u.view.dispatch({ effects: EditorView.scrollIntoView(head, { y: "center" }) }));
});

// ---- look ---------------------------------------------------------------------------------------------------

const theme = EditorView.theme({
  "&": { color: "var(--text)", backgroundColor: "transparent", fontSize: "var(--prose-size, 18px)", height: "100%" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--prose)", lineHeight: "1.7", overflow: "auto" },
  ".cm-content": { maxWidth: "var(--prose-width, 70ch)", margin: "0 auto", padding: "28px 4px 45vh", caretColor: "var(--accent)" },
  ".cm-line": { padding: "0" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, ::selection": {
    backgroundColor: "color-mix(in srgb, var(--accent) 28%, transparent) !important",
  },
  ".cm-placeholder": { color: "var(--muted)", fontStyle: "italic" },
  ".cm-dim": { opacity: "0.32", transition: "opacity .15s" },
  ".cm-near-miss": { textDecoration: "underline wavy var(--warn)", textDecorationSkipInk: "none", textUnderlineOffset: "4px" },
  ".cm-searchMatch": { backgroundColor: "var(--warn-soft)", outline: "1px solid var(--warn)" },
  ".cm-searchMatch.cm-searchMatch-selected": { backgroundColor: "var(--accent-soft)" },
  ".cm-panels": { backgroundColor: "var(--surface)", color: "var(--text)", fontFamily: "system-ui, sans-serif", fontSize: "13px" },
  ".cm-panels.cm-panels-top": { borderBottom: "1px solid var(--border)" },
  ".cm-panel.cm-search input, .cm-panel.cm-search button": { font: "inherit" },
  ".cm-textfield": { backgroundColor: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: "4px" },
  ".cm-button": { backgroundImage: "none", backgroundColor: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: "4px" },
  ".cm-tooltip": { border: "none", backgroundColor: "transparent" },
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
  world: WorldHooks;
  placeholderText?: string;
  readOnly?: boolean;
}

export interface Prose {
  view: EditorView;
  setFocusMode(on: boolean): void;
  setTypewriter(on: boolean): void;
  /** the world's names or the writing settings changed */
  refreshNames(): void;
  replaceDoc(text: string): void;
  replaceRange(from: number, to: number, text: string): void;
  destroy(): void;
}

export function createProse(parent: HTMLElement, opts: ProseOptions): Prose {
  const focusMode = new Compartment();
  const typewriterMode = new Compartment();
  const intentMode = new Compartment();
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
    namesPlugin(opts.world),
    intentMode.of(opts.readOnly ? [] : intent(opts.world)),
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
  ];
  const view = new EditorView({ parent, state: EditorState.create({ doc: opts.doc, extensions }) });
  return {
    view,
    setFocusMode: (on) => view.dispatch({ effects: focusMode.reconfigure(on ? focusPlugin : []) }),
    setTypewriter: (on) => view.dispatch({ effects: typewriterMode.reconfigure(on ? typewriter : []) }),
    refreshNames: () =>
      view.dispatch({ effects: [namesChanged.of(null), intentMode.reconfigure(opts.readOnly ? [] : intent(opts.world))] }),
    replaceDoc(text) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
    },
    replaceRange(from, to, text) {
      view.dispatch({ changes: { from, to, insert: text } });
    },
    destroy: () => view.destroy(),
  };
}
