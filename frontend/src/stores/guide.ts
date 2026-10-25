import { defineStore } from "pinia";

import { del, post } from "../api";
import { readLastUsed, writeLastUsed } from "../lastUsed";
import { DEFAULT_PREFS, PREFS_KEY, readPrefs, usePrefs } from "../prefs";
import { router } from "../router";
import type { World } from "../types";
import { bringIntoView, find, makeRoom, perform, sleep, waitFor, type Step, type Tour } from "../guide/engine";
import { TOURS } from "../guide/tours";
import { useSession } from "./session";

// The Guide (docs/SPEC.md §15): a walkthrough runs in a sandbox, a fresh copy of the demo world made for it, so
// nothing it does reaches the writer's own worlds. The sandbox stays after the walkthrough, to look around in, until
// the next walkthrough replaces it or it is deleted. Watched, the steps do themselves; tried, each waits for the
// writer to do it (or for "Do it for me").

const DONE_KEY = "quarry.guide";
const SPEED_KEY = "quarry.guide.speed";
/**
 * "instant": watched walkthroughs play without reading pauses, pointer travel or typing a letter at a time, still
 * doing every step and waiting for what each expects. Only the e2e run sets it (on the device), to keep CI quick.
 */
const PACE_KEY = "quarry.guide.pace";
/** when the page is dimmed around what a step points at: while watching (the default), always, or never */
const SPOT_KEY = "quarry.guide.spotlight";
export type Spotlight = "watching" | "always" | "never";
/** where a walkthrough had got to on this tab, so a reload can carry on */
const AT_KEY = "quarry.guide.at";

export type Mode = "watch" | "try";
export const SPEEDS = [0.5, 0.75, 1, 1.5, 2] as const;

function readJson<T>(store: Storage | undefined, key: string, fallback: T): T {
  try {
    const raw = store?.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function writeJson(store: Storage | undefined, key: string, value: unknown) {
  try {
    if (value === null) store?.removeItem(key);
    else store?.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: not remembered */
  }
}
const local = () => (typeof localStorage === "undefined" ? undefined : localStorage);
const session = () => (typeof sessionStorage === "undefined" ? undefined : sessionStorage);

/** What a sandbox left on this device (its keys, its entries in per-world maps), taken out when it goes. */
export function forgetSandbox(slug: string) {
  try {
    for (const k of Object.keys(localStorage)) {
      if (k.startsWith(DONE_KEY)) continue;
      if (k.includes(slug)) {
        localStorage.removeItem(k);
        continue;
      }
      const v: unknown = JSON.parse(localStorage.getItem(k) ?? "null");
      if (v && typeof v === "object" && !Array.isArray(v) && slug in v) {
        delete (v as Record<string, unknown>)[slug];
        localStorage.setItem(k, JSON.stringify(v));
      }
    }
  } catch {
    /* storage unavailable or not JSON: nothing to tidy */
  }
  if (readLastUsed().world === slug) writeLastUsed({});
}

/** The writer's own writing settings, kept aside while a walkthrough runs with the defaults. */
const PREFS_SAVED = "quarry.guide.prefs";

/**
 * A walkthrough runs with the default writing settings (the panel open, Focus mode off, Drafting, asking for a note),
 * so its steps find what they point at; the writer's own are kept aside, untouched, and put back when it stops, or at
 * the next load if the tab was closed in the middle.
 */
function useDefaultPrefs() {
  try {
    if (localStorage.getItem(PREFS_SAVED) === null) localStorage.setItem(PREFS_SAVED, localStorage.getItem(PREFS_KEY) ?? "");
  } catch {
    /* storage unavailable: the settings in memory are all there is */
  }
  usePrefs().$patch(structuredClone(DEFAULT_PREFS));
}

export function restoreWritingPrefs() {
  // the phone frame is Quarry too: only the page running the walkthrough looks after the settings
  if (typeof window !== "undefined" && window.top !== window) return;
  try {
    const saved = localStorage.getItem(PREFS_SAVED);
    if (saved === null) return;
    if (saved === "") localStorage.removeItem(PREFS_KEY);
    else localStorage.setItem(PREFS_KEY, saved);
    localStorage.removeItem(PREFS_SAVED);
  } catch {
    return;
  }
  usePrefs().$patch(readPrefs());
}

export interface Resumable {
  tour: string;
  mode: Mode;
  index: number;
  slug: string;
}

export const useGuide = defineStore("guide", {
  state: () => ({
    tour: null as Tour | null,
    mode: "watch" as Mode,
    index: 0,
    sandbox: null as World | null,
    /** making the sandbox */
    preparing: false,
    error: "",
    paused: false,
    speed: readJson<number>(local(), SPEED_KEY, 1),
    instant: readJson<string>(local(), PACE_KEY, "") === "instant",
    /** the caption folded to its title line, to see what it covers */
    folded: false,
    spotlight: readJson<Spotlight>(local(), SPOT_KEY, "watching"),
    /** the step's target is in view and settled: its ring and caption show */
    shown: true,
    /** what the next step will use, if it is already on the page: the caption keeps clear of it */
    upcoming: null as HTMLElement | null,
    /** the phone's address, when it is open */
    phone: null as string | null,
    /** the element the step points at, on the page or in the phone */
    target: null as HTMLElement | null,
    /** the fake pointer, in page coordinates */
    pointer: null as { x: number; y: number; pressed: boolean } | null,
    /** the walkthrough reached its end */
    finished: false,
    /** steps that couldn't find what they point at or wait for: a walkthrough gone stale (the e2e run checks) */
    missed: [] as string[],
    done: readJson<Record<string, string>>(local(), DONE_KEY, {}),
    /** a walkthrough this tab was in the middle of before a reload */
    resumable: readJson<Resumable | null>(session(), AT_KEY, null),
  }),
  getters: {
    step: (s): Step | null => s.tour?.steps[s.index] ?? null,
    active: (s) => !!s.tour,
  },
  actions: {
    async start(id: string, mode: Mode) {
      const tour = TOURS.find((t) => t.id === id);
      if (!tour || this.preparing) return;
      this.stop();
      this.preparing = true;
      this.error = "";
      try {
        // the last sandbox goes (the server deletes it), with what it left here
        for (const w of useSession().worlds.filter((x) => x.sandbox)) {
          useSession().dropWorld(w.slug);
          forgetSandbox(w.slug);
        }
        const world = await post<World>("/api/guide/sandbox");
        useSession().putWorld(world);
        this.begin(tour, mode, world, 0);
      } catch {
        this.error = "Couldn't make the sandbox. Try again in a moment.";
      } finally {
        this.preparing = false;
      }
    },

    /** Carry on after a reload, in the same sandbox, from the step it had reached. */
    async resume() {
      const at = this.resumable;
      const tour = TOURS.find((t) => t.id === at?.tour);
      const world = at && useSession().world(at.slug);
      if (!at || !tour || !world?.sandbox) {
        this.resumable = null;
        writeJson(session(), AT_KEY, null);
        return;
      }
      // the page the walkthrough was on: the last address a step opened, up to the one it reached
      const go = tour.steps.slice(0, at.index + 1).reverse().find((s) => s.go)?.go;
      if (go) await router.push(go.replace("{w}", world.slug));
      this.begin(tour, at.mode, world, at.index);
    },

    begin(tour: Tour, mode: Mode, world: World, index: number) {
      Object.assign(this, { tour, mode, index, sandbox: world, paused: false, finished: false, folded: false, phone: null, missed: [], resumable: null });
      useDefaultPrefs();
      run += 1;
      void this.loop(run);
    },

    /** Stop the walkthrough. The sandbox stays, to look around in; the next walkthrough or "Delete" removes it. */
    stop() {
      run += 1;
      makeRoom(document, 0);
      leave();
      if (this.finished && this.tour) {
        this.done = { ...this.done, [this.tour.id]: new Date().toISOString() };
        writeJson(local(), DONE_KEY, this.done);
      }
      writeJson(session(), AT_KEY, null);
      restoreWritingPrefs();
      Object.assign(this, { tour: null, phone: null, target: null, pointer: null, finished: false, resumable: null });
    },

    /** Delete the sandbox, from the Guide page or its notice. */
    async clear() {
      this.stop();
      const here = router.currentRoute.value.params.world;
      for (const w of useSession().worlds.filter((x) => x.sandbox)) {
        useSession().dropWorld(w.slug);
        forgetSandbox(w.slug);
        if (here === w.slug) await router.push({ name: "guide" });
      }
      this.sandbox = null;
      await del("/api/guide/sandbox").catch(() => undefined);
    },

    setSpotlight(v: Spotlight) {
      this.spotlight = v;
      writeJson(local(), SPOT_KEY, v);
    },
    setSpeed(v: number) {
      this.speed = v;
      writeJson(local(), SPEED_KEY, v);
    },
    pause() {
      this.paused = !this.paused;
    },
    /** On to the next step: watched, without waiting; tried, doing this one for the writer. */
    next() {
      advance?.("next");
    },

    /** The element the next step will use, when it is on this page already (not after an address or the phone). */
    nextTarget(): HTMLElement | null {
      const now = this.step;
      const next = this.tour?.steps[this.index + 1];
      if (!now || !next?.target || next.go || next.phone !== undefined || (next.in ?? "desk") !== (now.in ?? "desk")) return null;
      const d = this.doc();
      return d ? find(d, next.target) : null;
    },

    doc(): Document | null {
      if (this.step?.in !== "phone") return document;
      const frame = document.querySelector<HTMLIFrameElement>("[data-testid=guide-phone-frame]");
      return frame?.contentDocument ?? null;
    },

    async loop(me: number) {
      const stopped = () => me !== run;
      while (!stopped() && this.tour && this.index < this.tour.steps.length) {
        writeJson(session(), AT_KEY, { tour: this.tour.id, mode: this.mode, index: this.index, slug: this.sandbox!.slug });
        try {
          await this.play(this.tour.steps[this.index]!, stopped);
        } catch (e) {
          // a step that fails is noted and skipped, so the walkthrough carries on
          this.missed.push(`${this.index + 1}: ${e instanceof Error ? e.message : String(e)}`);
        }
        if (stopped()) return;
        this.index += 1;
      }
      if (!stopped()) {
        leave();
        writeJson(session(), AT_KEY, null);
        this.finished = true;
        this.shown = true;
        this.target = null;
        this.pointer = null;
      }
    },

    async play(step: Step, stopped: () => boolean) {
      const w = this.sandbox!.slug;
      this.target = null;
      this.upcoming = null;
      this.shown = false;
      // the pointer shows only while a step acts, so it never points somewhere the caption isn't about
      this.pointer = null;
      leave();
      if (step.phone !== undefined) this.phone = step.phone ? step.phone.replace("{w}", w) : null;
      if (step.go) await router.push(step.go.replace("{w}", w));
      const doc = () => this.doc();
      const el = step.target ? await waitFor(doc, step.target, 15_000, stopped) : null;
      if (stopped()) return;
      if (step.target && !el) this.missed.push(`${this.index + 1}: ${step.target.css} ${step.target.text ?? ""}`.trim());
      // scrolled into view first; the ring and the caption show once it has settled
      if (el) await bringIntoView(el, { smooth: !this.instant, stopped });
      if (stopped()) return;
      this.target = el;
      this.upcoming = this.nextTarget();
      this.shown = true;

      // wait for the writer (tried), or for the time to read the caption (watched); Next cuts either short
      const cleanups: (() => void)[] = [];
      const how = await new Promise<"time" | "next" | "did">((resolve) => {
        advance = resolve;
        if (this.mode === "watch") {
          void this.linger(step, stopped).then(() => resolve("time"));
        } else if (el && step.act && "click" in step.act) {
          // their own click on the highlighted part counts
          const onClick = (e: Event) => el.contains(e.target as Node) && resolve("did");
          el.ownerDocument.addEventListener("click", onClick, true);
          cleanups.push(() => el.ownerDocument.removeEventListener("click", onClick, true));
        } else if (step.act && step.wait) {
          // they typed or selected it themselves: what follows shows
          let gone = false;
          cleanups.push(() => (gone = true));
          void waitFor(doc, step.wait, 60 * 60_000, () => gone || stopped()).then((x) => x && resolve("did"));
        }
      });
      advance = null;
      for (const c of cleanups) c();
      if (stopped()) return;

      // Next on a step that does something does it, so the steps after it find what they expect
      const acting = !!(step.act && el && how !== "did");
      if (acting) {
        await this.pointAt(el!, stopped);
        if (step.act && "hover" in step.act) hovered = el;
        await perform(el!, step.act!, { slow: this.mode === "watch" && !this.instant, speed: this.speed, stopped });
      }
      if (step.wait && (acting || how === "did") && !(await waitFor(doc, step.wait, 15_000, stopped)) && !stopped()) {
        this.missed.push(`${this.index + 1}: waited for ${step.wait.css} ${step.wait.text ?? ""}`.trim());
      }
      await sleep(this.instant ? 0 : how === "did" ? 300 : 150);
    },

    /** Watched: the caption's time on screen at the chosen speed, held while paused. */
    async linger(step: Step, stopped: () => boolean) {
      if (this.instant) return sleep(step.settle ?? 0);
      let left = (step.read ?? Math.min(9000, 1600 + step.say.length * 38)) / this.speed;
      while (left > 0 && !stopped()) {
        await sleep(100);
        if (!this.paused) left -= 100;
      }
    },

    /** Move the fake pointer onto `el` and press, so a watched click can be followed. */
    async pointAt(el: HTMLElement, stopped: () => boolean) {
      if (this.mode !== "watch" || this.instant) return;
      const r = el.getBoundingClientRect();
      const off = this.step?.in === "phone" ? document.querySelector("[data-testid=guide-phone-frame]")!.getBoundingClientRect() : { left: 0, top: 0 };
      const x = off.left + r.left + Math.min(r.width / 2, 40);
      const y = off.top + r.top + Math.min(r.height / 2, 14);
      this.pointer = { x, y, pressed: false };
      await sleep(650 / this.speed);
      if (stopped()) return;
      this.pointer = { x, y, pressed: true };
      await sleep(180 / this.speed);
      this.pointer = { x, y, pressed: false };
    },
  },
});

// outside the store: these never need to be reactive
let run = 0;
let advance: ((how: "time" | "next" | "did") => void) | null = null;
/** the element a step rested the pointer on: it is left when the walkthrough moves on */
let hovered: HTMLElement | null = null;

function leave() {
  const el = hovered;
  hovered = null;
  if (!el?.isConnected) return;
  const win = el.ownerDocument.defaultView ?? window;
  el.dispatchEvent(new win.PointerEvent("pointerleave", { pointerType: "mouse" }));
  el.dispatchEvent(new win.PointerEvent("pointerout", { pointerType: "mouse", bubbles: true }));
  el.dispatchEvent(new win.MouseEvent("mouseout", { bubbles: true }));
}
