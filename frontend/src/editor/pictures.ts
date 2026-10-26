// Picture lines in the editor (docs/SPEC.md §17.3). The line stays text that can be typed in; with the cursor elsewhere
// its `(picture:…)` is folded into a small chip, one unit for the cursor and for Backspace, and the picture is drawn
// under it as a block. The block's height is reserved from the picture's stored size, so nothing jumps when it loads,
// and the decorations are worked out again only when a change touches a picture line (or the cursor moves onto or
// off one): typing anywhere else never redraws a picture.

import { EditorState, Prec, RangeSet, RangeSetBuilder, StateEffect, StateField, type Extension, type Transaction } from "@codemirror/state";
import { Decoration, EditorView, WidgetType, keymap, type DecorationSet } from "@codemirror/view";

import { imageFiles, pictureLine, pictureUrl, type Missing, type PictureInfo } from "../pictures";

export interface PictureHooks {
  /** the picture's name and size, when it is one of this world's */
  info(id: string): PictureInfo | undefined;
  /** why it can't be shown, when known: deleted, of another world, or not on this device */
  missing(id: string): Missing | undefined;
  /** the full view (docs/SPEC.md §17.2) */
  open(id: string, caption: string): void;
  /** upload a pasted or dropped file; throws with the sentence to show */
  upload?(file: File): Promise<PictureInfo>;
  /** "Uploading harbour.jpg…" at the foot, an error, or null when done */
  status?(text: string | null, error?: boolean): void;
}

/** The world's pictures became known (or a picture went missing): draw the lines again. */
export const picturesChanged = StateEffect.define<null>();

const LINK = "](picture:";
const isPictureText = (text: string) => text.includes(LINK) && pictureLine(text) !== null;

/** Is this line of the editor a picture line? (Names aren't matched in it.) */
export const onPictureLine = (text: string) => isPictureText(text);

class Chip extends WidgetType {
  eq() {
    return true;
  }
  toDOM() {
    const s = document.createElement("span");
    s.className = "cm-picture-chip";
    s.textContent = "▣";
    s.title = "A picture: the line shows in full with the cursor on it";
    return s;
  }
  ignoreEvent() {
    return false;
  }
}
const chip = Decoration.replace({ widget: new Chip() });
const pictureLineDeco = Decoration.line({ class: "cm-picture-line", attributes: { spellcheck: "false" } });

const WHY: Record<Missing, string> = {
  deleted: "Picture deleted",
  elsewhere: "Not a picture of this world",
  offline: "Not on this device",
};

class Block extends WidgetType {
  constructor(
    readonly id: string,
    readonly caption: string,
    readonly info: PictureInfo | undefined,
    readonly why: Missing | undefined,
    readonly hooks: PictureHooks,
  ) {
    super();
  }
  eq(o: Block) {
    return o.id === this.id && o.caption === this.caption && o.why === this.why && o.info?.width === this.info?.width && o.info?.height === this.info?.height;
  }
  get estimatedHeight() {
    const w = this.info?.width ?? 0;
    const h = this.info?.height ?? 0;
    const room = typeof window !== "undefined" ? window.innerHeight * 0.6 : 400;
    return (w && h ? Math.min((640 * h) / w, room, h) : 48) + (this.caption ? 30 : 12);
  }
  toDOM() {
    return pictureFigure(this.id, this.caption, this.info, this.why, () => this.hooks.open(this.id, this.caption));
  }
  ignoreEvent() {
    return true;
  }
}

/** A picture with its caption, its box shaped before it loads; also used on read-only pages. */
export function pictureFigure(id: string, caption: string, info: PictureInfo | undefined, why: Missing | undefined, open?: () => void): HTMLElement {
  const fig = document.createElement("figure");
  fig.className = "cm-picture picture-figure";
  fig.dataset.picture = id;
  fig.dataset.testid = "picture-block";
  const box = document.createElement("div");
  box.className = "picture-box";
  const w = info?.width ?? 0;
  const h = info?.height ?? 0;
  if (w && h) {
    box.style.aspectRatio = `${w} / ${h}`;
    box.style.width = `min(100%, ${w}px, calc(60vh * ${(w / h).toFixed(4)}))`;
  } else box.classList.add("short");
  const say = (text: string) => {
    box.replaceChildren();
    box.classList.add("missing");
    const s = document.createElement("span");
    s.className = "picture-why";
    s.textContent = text;
    box.append(s);
    fig.dataset.missing = text;
  };
  if (why || !info) say(why ? WHY[why] : typeof navigator !== "undefined" && navigator.onLine === false ? WHY.offline : "Loading…");
  else {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = caption || info.name;
    img.src = pictureUrl(id, "view");
    img.addEventListener("error", () => say(navigator.onLine === false ? WHY.offline : "Can't be shown"));
    box.append(img);
    if (open) {
      box.classList.add("opens");
      box.addEventListener("click", (e) => {
        e.preventDefault();
        open();
      });
    }
  }
  fig.append(box);
  if (caption) {
    const c = document.createElement("figcaption");
    c.textContent = caption;
    fig.append(c);
  }
  return fig;
}

interface Built {
  decos: DecorationSet;
  folds: RangeSet<Decoration>;
}

function build(state: EditorState, hooks: PictureHooks, focused: boolean): Built {
  const decos = new RangeSetBuilder<Decoration>();
  const folds = new RangeSetBuilder<Decoration>();
  const here = state.doc.lineAt(state.selection.main.head).number;
  let pos = 0;
  let n = 0;
  for (const text of state.doc.iterLines()) {
    n++;
    if (text.includes(LINK)) {
      const p = pictureLine(text);
      if (p) {
        const from = pos;
        const to = pos + text.length;
        decos.add(from, from, pictureLineDeco);
        if (n !== here || !focused) {
          const at = from + text.indexOf(LINK) + 1;
          const end = at + "(picture:".length + p.id.length + 1;
          decos.add(at, end, chip);
          folds.add(at, end, chip);
        }
        const info = hooks.info(p.id);
        decos.add(to, to, Decoration.widget({ widget: new Block(p.id, p.caption, info, hooks.missing(p.id), hooks), block: true, side: 1 }));
      }
    }
    pos += text.length + 1;
  }
  return { decos: decos.finish(), folds: folds.finish() };
}

/** Did a change touch a line that is (or was) a picture line? Anything else only moves the pictures along. */
function touchesPictures(tr: Transaction): boolean {
  let touched = false;
  tr.changes.iterChangedRanges((fA, tA, fB, tB) => {
    if (touched) return;
    const a = tr.startState.doc;
    const b = tr.state.doc;
    touched = a.sliceString(a.lineAt(fA).from, a.lineAt(tA).to).includes(LINK) || b.sliceString(b.lineAt(fB).from, b.lineAt(tB).to).includes(LINK);
  });
  return touched;
}

const focusChanged = StateEffect.define<boolean>();

export function pictureExtensions(hooks: PictureHooks): Extension {
  let focused = false;
  const field = StateField.define<Built>({
    create: (state) => build(state, hooks, focused),
    update(value, tr) {
      const focus = tr.effects.find((e) => e.is(focusChanged));
      if (focus) focused = focus.value;
      if (focus || tr.effects.some((e) => e.is(picturesChanged))) return build(tr.state, hooks, focused);
      if (tr.docChanged && touchesPictures(tr)) return build(tr.state, hooks, focused);
      if (tr.selection || tr.docChanged) {
        const before = tr.startState.doc.lineAt(tr.startState.selection.main.head);
        const after = tr.state.doc.lineAt(tr.state.selection.main.head);
        if ((before.number !== after.number || tr.docChanged) && (isPictureText(before.text) || isPictureText(after.text))) return build(tr.state, hooks, focused);
      }
      return tr.docChanged ? { decos: value.decos.map(tr.changes), folds: value.folds.map(tr.changes) } : value;
    },
    provide: (f) => [EditorView.decorations.from(f, (v) => v.decos), EditorView.atomicRanges.of((view) => view.state.field(f).folds)],
  });
  return [
    field,
    // the link is one unit for Backspace whether it is folded or shown in full (docs/SPEC.md §17.3)
    Prec.high(keymap.of([{ key: "Backspace", run: deleteLinkBefore }])),
    EditorView.focusChangeEffect.of((_state, focusing) => focusChanged.of(focusing)),
    EditorView.domEventHandlers({
      paste(e, view) {
        const files = imageFiles(e.clipboardData);
        if (!files.length || !hooks.upload || view.state.readOnly) return false;
        e.preventDefault();
        void addPictures(view, files, hooks);
        return true;
      },
      drop(e, view) {
        const files = imageFiles(e.dataTransfer);
        if (!files.length || !hooks.upload || view.state.readOnly) return false;
        e.preventDefault();
        const at = view.posAtCoords({ x: e.clientX, y: e.clientY });
        if (at !== null) view.dispatch({ selection: { anchor: at } });
        void addPictures(view, files, hooks);
        return true;
      },
    }),
  ];
}

const LINK_BEFORE = /\(picture:[0-9a-f-]{36}\)$/;

/** Backspace just after a picture line's `(picture:…)` deletes all of it (Undo brings it back). */
function deleteLinkBefore(view: EditorView): boolean {
  const sel = view.state.selection.main;
  if (!sel.empty || view.state.readOnly) return false;
  const line = view.state.doc.lineAt(sel.head);
  const before = line.text.slice(0, sel.head - line.from);
  const m = LINK_BEFORE.exec(before);
  if (!m || !isPictureText(line.text)) return false;
  view.dispatch({ changes: { from: sel.head - m[0].length, to: sel.head }, userEvent: "delete.backward" });
  return true;
}

/** A picture line after the paragraph the cursor is in, with the cursor between the brackets for a caption. */
export function insertPictureLine(view: EditorView, id: string): void {
  const line = view.state.doc.lineAt(view.state.selection.main.head);
  const link = `![](picture:${id})`;
  if (!line.text.trim()) {
    view.dispatch({ changes: { from: line.from, to: line.to, insert: link }, selection: { anchor: line.from + 2 }, scrollIntoView: true });
  } else {
    const insert = `\n\n${link}`;
    view.dispatch({ changes: { from: line.to, insert }, selection: { anchor: line.to + 4 }, scrollIntoView: true });
  }
  view.focus();
}

/** Upload the files one after another, each becoming a picture line when it is done (docs/SPEC.md §17.3). */
export async function addPictures(view: EditorView, files: File[], hooks: PictureHooks): Promise<void> {
  for (const file of files) {
    hooks.status?.(`Uploading ${file.name || "a picture"}…`);
    try {
      const p = await hooks.upload!(file);
      if (!view.dom.isConnected) return;
      view.dispatch({ effects: picturesChanged.of(null) });
      insertPictureLine(view, p.id);
      hooks.status?.(null);
    } catch (e) {
      hooks.status?.((e as Error).message, true);
      return;
    }
  }
}
