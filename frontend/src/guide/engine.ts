// The Guide's steps (docs/SPEC.md §15): what a walkthrough says, where it points and what it does, and the few
// actions it can take on the real page — the same clicks and keys a writer would make. Nothing here knows any view's
// insides beyond the data-testids and labels the e2e tests already rely on.

import { EditorView } from "@codemirror/view";

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
  | { choose: string }
  | { key: string }
  /** in the chapter editor: select the paragraph holding this text */
  | { selectText: string };

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

export const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Look for `t` until it shows, up to `ms`; null if it never does or `stopped()` says to give up. */
export async function waitFor(doc: () => Document | null, t: Target, ms = 15_000, stopped = () => false): Promise<HTMLElement | null> {
  const end = Date.now() + ms;
  while (Date.now() < end && !stopped()) {
    const d = doc();
    const el = d && find(d, t);
    if (el) return el;
    await sleep(120);
  }
  return null;
}

/** A plain-words line for the try-it-yourself hint. */
export function hint(act: Act | undefined): string {
  if (!act) return "";
  if ("click" in act) return act.shift ? "Shift-click the highlighted button." : "Click the highlighted part.";
  if ("hover" in act) return "Rest the pointer on the highlighted part.";
  if ("fill" in act) return `Type “${act.fill}”.`;
  if ("choose" in act) return `Choose “${act.choose}”.`;
  if ("key" in act) return `Press ${act.key}.`;
  return "Select the highlighted paragraph.";
}

function setValue(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
  // through the prototype's setter, so Vue's v-model sees the change (the phone's elements are another window's)
  const proto = Object.getPrototypeOf(el) as object;
  Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

/** Do what a step does, on `el`. Watched typing goes a letter at a time so it can be followed. */
export async function perform(el: HTMLElement, act: Act, opts: { slow: boolean; stopped: () => boolean }): Promise<void> {
  const win = el.ownerDocument.defaultView ?? window;
  if ("click" in act) {
    if (act.shift) el.dispatchEvent(new win.MouseEvent("click", { bubbles: true, cancelable: true, shiftKey: true }));
    else el.click();
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
      await sleep(28);
    }
  } else if ("choose" in act) {
    const sel = el as HTMLSelectElement;
    sel.value = act.choose;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  } else if ("key" in act) {
    el.dispatchEvent(new win.KeyboardEvent("keydown", { key: act.key, bubbles: true, cancelable: true }));
  } else {
    const view = EditorView.findFromDOM(el.closest(".cm-editor") ?? el);
    if (!view) return;
    const doc = view.state.doc;
    const at = doc.toString().indexOf(act.selectText);
    if (at < 0) return;
    const line = doc.lineAt(at);
    view.dispatch({ selection: { anchor: line.from, head: line.to }, effects: EditorView.scrollIntoView(line.from, { y: "center" }) });
  }
}
