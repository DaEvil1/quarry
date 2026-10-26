// The Guide's steps (docs/SPEC.md §15): what a walkthrough says, where it points and what it does, and the few
// actions it can take on the real page — the same clicks and keys a writer would make. Nothing here knows any view's
// insides beyond the data-testids and labels the e2e tests already rely on.

import { EditorView } from "@codemirror/view";

import { comfortable } from "./place";

/** An element on the page: a CSS selector, narrowed to the ones holding `text`, and the `nth` of those. */
export interface Target {
  css: string;
  text?: string;
  nth?: number;
}

export type Act =
  | { click: true; shift?: boolean }
  /** rest the pointer on it (the Timeline's marks draw their cause arrows that way) */
  | { hover: true }
  /** typed into an input or textarea, a letter at a time when watched */
  | { fill: string }
  /** an option of a select, by its value or the words it shows */
  | { choose: string }
  /** a key, with modifiers: sent to the highlighted element (the editor's own shortcuts listen there) */
  | { key: string; ctrl?: boolean; shift?: boolean; alt?: boolean }
  /** in the editor: select the paragraph holding this text, or just these words with `exact` */
  | { selectText: string; exact?: boolean }
  /** in the editor: put the cursor just after this text (or before it, with `before`) */
  | { cursorAt: string; before?: boolean }
  /** in the editor: type at the cursor, a letter at a time when watched */
  | { type: string };

export interface Step {
  /** what the step says: one or two short sentences */
  say: string;
  /** open this address first, `{w}` standing for the sandbox world's address */
  go?: string;
  /** open the phone (at this address) or close it */
  phone?: string | false;
  /** where `target` and `wait` are looked for: the page or the phone */
  in?: "desk" | "phone";
  target?: Target;
  act?: Act;
  /** after the act, move on once this shows */
  wait?: Target;
  /** how long a watched step lingers before acting, in ms (else worked out from the caption's length) */
  read?: number;
  /** time the app itself needs here, in ms (a debounced count, say), kept at every pace, the instant one too */
  settle?: number;
}

export interface Tour {
  id: string;
  title: string;
  /** one line: what it shows */
  blurb: string;
  minutes: number;
  /** the parts of Quarry it touches, for the Guide page */
  covers: string[];
  steps: Step[];
}

export function find(doc: Document, t: Target): HTMLElement | null {
  let all = [...doc.querySelectorAll<HTMLElement>(t.css)];
  if (t.text) all = all.filter((e) => (e.textContent ?? "").includes(t.text!));
  // hidden ones (the phone tab bar at the desk, say) don't count
  all = all.filter((e) => e.getClientRects().length > 0);
  return all[t.nth ?? 0] ?? null;
}

const KEY_CODES: Record<string, number> = { Enter: 13, Escape: 27, Tab: 9, " ": 32, F8: 119, ArrowUp: 38, ArrowDown: 40, ArrowLeft: 37, ArrowRight: 39 };

/** CodeMirror's and Quarry's Mod- shortcuts are Cmd on a Mac: a step's `ctrl` follows. */
const mac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

export const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Look for `t` until it shows, up to `ms`; null if it never does or `stopped()` says to give up. */
export async function waitFor(doc: () => Document | null, t: Target, ms = 15_000, stopped = () => false): Promise<HTMLElement | null> {
  const end = Date.now() + ms;
  let revealed = 0;
  while (Date.now() < end && !stopped()) {
    const d = doc();
    const el = d && find(d, t);
    if (el) return el;
    // a line of a long text is only drawn near the screen: bring it there (once a second at most)
    if (d && Date.now() - revealed > 1000) {
      revealed = Date.now();
      revealLine(d, t);
    }
    await sleep(50);
  }
  return null;
}

/** For a target that is an editor's line holding some text: scroll that text into the editor's view, so it is drawn. */
function revealLine(doc: Document, t: Target) {
  const at = t.css.lastIndexOf(".cm-line");
  if (at < 0 || !t.text) return;
  const scope = t.css.slice(0, at).trim();
  for (const dom of doc.querySelectorAll<HTMLElement>(scope ? `${scope} .cm-editor, ${scope}.cm-editor` : ".cm-editor")) {
    const view = EditorView.findFromDOM(dom);
    const pos = view ? view.state.doc.toString().indexOf(t.text) : -1;
    if (view && pos >= 0) {
      view.dispatch({ effects: EditorView.scrollIntoView(pos, { y: "center" }) });
      return;
    }
  }
}

/** A plain-words line for the try-it-yourself hint. */
export function hint(act: Act | undefined): string {
  if (!act) return "";
  if ("click" in act) return act.shift ? "Shift-click the highlighted button." : "Click the highlighted part.";
  if ("hover" in act) return "Rest the pointer on the highlighted part.";
  if ("fill" in act) return `Type “${act.fill}”.`;
  if ("choose" in act) return `Choose “${act.choose}”.`;
  if ("key" in act) return `Press ${[act.ctrl && (mac() ? "Cmd" : "Ctrl"), act.alt && "Alt", act.shift && "Shift", act.key].filter(Boolean).join("+")}.`;
  if ("type" in act) return `Type “${act.type}”.`;
  if ("cursorAt" in act) return `Click ${act.before ? "before" : "just after"} “${act.cursorAt}”.`;
  return act.exact ? `Select “${act.selectText}”.` : "Select the highlighted paragraph.";
}

function setValue(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
  // through the prototype's setter, so Vue's v-model sees the change (the phone's elements are another window's)
  const proto = Object.getPrototypeOf(el) as object;
  Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

/** Do what a step does, on `el`. Watched typing goes a letter at a time so it can be followed. */
export async function perform(el: HTMLElement, act: Act, opts: { slow: boolean; speed?: number; stopped: () => boolean }): Promise<void> {
  const pace = 28 / (opts.speed ?? 1);
  const win = el.ownerDocument.defaultView ?? window;
  if ("click" in act) {
    // SVG elements (the Timeline's marks, the chart's places) have no click(): a click event does the same
    if (act.shift || typeof el.click !== "function") {
      const r = el.getBoundingClientRect();
      const at = { clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
      el.dispatchEvent(new win.MouseEvent("click", { ...at, bubbles: true, cancelable: true, shiftKey: !!act.shift }));
    } else el.click();
  } else if ("hover" in act) {
    const r = el.getBoundingClientRect();
    const at = { clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, pointerType: "mouse" };
    el.dispatchEvent(new win.PointerEvent("pointerover", { ...at, bubbles: true }));
    el.dispatchEvent(new win.PointerEvent("pointerenter", at));
    el.dispatchEvent(new win.MouseEvent("mouseover", { ...at, bubbles: true }));
  } else if ("fill" in act) {
    const box = el as HTMLInputElement | HTMLTextAreaElement;
    box.focus();
    if (!opts.slow) return setValue(box, act.fill);
    setValue(box, "");
    for (let i = 1; i <= act.fill.length && !opts.stopped(); i++) {
      setValue(box, act.fill.slice(0, i));
      await sleep(pace);
    }
  } else if ("choose" in act) {
    // by value, or by the words the option shows (an era's name, where its value is an id)
    const sel = el as HTMLSelectElement;
    const opts = [...sel.options];
    const opt = opts.find((o) => o.value === act.choose) ?? opts.find((o) => o.text.trim() === act.choose)
      ?? (act.choose ? opts.find((o) => o.text.includes(act.choose)) : undefined);
    if (!opt) throw new Error(`no “${act.choose}” to choose`);
    sel.value = opt.value;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  } else if ("key" in act) {
    // as a real keyboard sends it: a shifted letter is a capital, and CodeMirror reads Mod-Shift-s by the key's code
    const letter = /^[a-z]$/i.test(act.key);
    const key = letter && act.shift ? act.key.toUpperCase() : act.key;
    const code = letter ? `Key${act.key.toUpperCase()}` : act.key;
    const keyCode = letter ? act.key.toUpperCase().charCodeAt(0) : (KEY_CODES[act.key] ?? 0);
    el.dispatchEvent(new win.KeyboardEvent("keydown", {
      key, code, keyCode, which: keyCode, ctrlKey: !!act.ctrl && !mac(), metaKey: !!act.ctrl && mac(), shiftKey: !!act.shift, altKey: !!act.alt, bubbles: true, cancelable: true,
    }));
  } else {
    const view = editorOf(el);
    if (!view) throw new Error("no editor here");
    const doc = view.state.doc;
    const text = "type" in act ? "" : "cursorAt" in act ? act.cursorAt : act.selectText;
    const at = doc.toString().indexOf(text);
    if (at < 0) throw new Error(`“${text}” isn't in the text`);
    if ("type" in act) {
      view.focus();
      for (let i = 0; i < act.type.length && !opts.stopped(); i += opts.slow ? 1 : act.type.length) {
        const chunk = opts.slow ? act.type[i]! : act.type;
        const pos = view.state.selection.main.head;
        view.dispatch({ changes: { from: pos, insert: chunk }, selection: { anchor: pos + chunk.length }, userEvent: "input.type" });
        if (opts.slow) await sleep(pace * 1.6);
      }
    } else if ("cursorAt" in act) {
      const pos = act.before ? at : at + text.length;
      view.focus();
      view.dispatch({ selection: { anchor: pos }, effects: EditorView.scrollIntoView(pos, { y: "center" }) });
    } else if (act.exact) {
      view.dispatch({ selection: { anchor: at, head: at + text.length }, effects: EditorView.scrollIntoView(at, { y: "center" }) });
    } else {
      const line = doc.lineAt(at);
      view.dispatch({ selection: { anchor: line.from, head: line.to }, effects: EditorView.scrollIntoView(line.from, { y: "center" }) });
    }
  }
}

/** Room under the page for `bringIntoView` (none when `px` is 0 or less), kept until the next step needs other room or
 * the walkthrough stops. */
export function makeRoom(doc: Document, px: number): void {
  let room = doc.getElementById("guide-room");
  if (px <= 0) {
    room?.remove();
    return;
  }
  if (!room) {
    room = doc.createElement("div");
    room.id = "guide-room";
    room.setAttribute("aria-hidden", "true");
    doc.body.appendChild(room);
  }
  room.style.height = `${Math.ceil(px)}px`;
}

/** The CodeMirror view an element is in (or the page's editor, for a step that points elsewhere). */
function editorOf(el: HTMLElement): EditorView | null {
  const dom = el.closest(".cm-editor") ?? el.ownerDocument.querySelector(".cm-editor");
  return dom ? EditorView.findFromDOM(dom as HTMLElement) : null;
}

/** One frame of `win` (or 50 ms, in a tab the browser isn't drawing). */
function frame(win: Window): Promise<void> {
  return new Promise((done) => {
    const t = setTimeout(done, 50);
    win.requestAnimationFrame(() => {
      clearTimeout(t);
      done();
    });
  });
}

/**
 * Bring what a step points at into view before it is shown (docs/SPEC.md §15.1): if it isn't comfortably on screen,
 * scroll it to the middle (a tall one to the top), through any scrolling boxes it sits in, smoothly unless `smooth`
 * is off (the instant pace, or a writer who asks for reduced motion), and wait until it has stopped moving.
 */
export async function bringIntoView(el: HTMLElement, opts: { smooth: boolean; stopped: () => boolean }): Promise<void> {
  const win = el.ownerDocument.defaultView ?? window;
  const view = { width: win.innerWidth, height: win.innerHeight };
  const r0 = el.getBoundingClientRect();
  if (comfortable(r0, view)) return;
  const reduced = win.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  const smooth = opts.smooth && !reduced;
  const start = r0.height > view.height * 0.6;
  // a target low on a page that ends soon after it can't be scrolled up to where a caption fits: room under the page
  const want = start ? 0 : Math.max(0, (view.height - r0.height) / 2);
  const scroller = el.ownerDocument.scrollingElement ?? el.ownerDocument.documentElement;
  const had = el.ownerDocument.getElementById("guide-room")?.offsetHeight ?? 0;
  const left = scroller.scrollHeight - had - win.innerHeight - win.scrollY;
  makeRoom(el.ownerDocument, r0.top - want - left);
  el.scrollIntoView({ block: start ? "start" : "center", inline: "nearest", behavior: smooth ? "smooth" : "auto" });
  // settled: three frames in a row without moving
  const end = Date.now() + (smooth ? 1500 : 300);
  let last = el.getBoundingClientRect();
  let still = 0;
  while (Date.now() < end && !opts.stopped() && still < 3) {
    await frame(win);
    const r = el.getBoundingClientRect();
    still = Math.abs(r.top - last.top) < 0.5 && Math.abs(r.left - last.left) < 0.5 ? still + 1 : 0;
    last = r;
  }
}
