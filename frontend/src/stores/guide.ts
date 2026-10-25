import { defineStore } from "pinia";

import { del, post } from "../api";
import { readLastUsed, writeLastUsed } from "../lastUsed";
import { router } from "../router";
import type { World } from "../types";
import { perform, sleep, waitFor, type Step, type Tour } from "../guide/engine";
import { TOURS } from "../guide/tours";
import { useSession } from "./session";

// The Guide (docs/SPEC.md §15): a walkthrough runs in a sandbox, a fresh copy of the demo world made for it and
// deleted when it ends, so nothing it does reaches the writer's own worlds. Watched, the steps do themselves; tried,
// each waits for the writer to do it (or for "Do it for me").

const DONE_KEY = "quarry.guide";

export type Mode = "watch" | "try";

function readDone(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(DONE_KEY) ?? "{}") as Record<string, string>;
  } catch {
    return {};
  }
}

/** This device's storage before the walkthrough, so what the sandbox leaves in it can be taken out again. */
function storageKeys(): Set<string> {
  try {
    return new Set(Object.keys(localStorage));
  } catch {
    return new Set();
  }
}

function forgetSandbox(slug: string, before: Set<string>) {
  try {
    for (const k of Object.keys(localStorage)) {
      if (k === DONE_KEY) continue;
      if (!before.has(k) || k.includes(slug)) {
        localStorage.removeItem(k);
        continue;
      }
      // per-world maps ({"<world>": …}): drop the sandbox's entry
      const v: unknown = JSON.parse(localStorage.getItem(k) ?? "null");
      if (v && typeof v === "object" && !Array.isArray(v) && slug in v) {
        delete (v as Record<string, unknown>)[slug];
        localStorage.setItem(k, JSON.stringify(v));
      }
    }
  } catch {
    /* storage unavailable or not JSON: nothing to tidy */
  }
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
    done: readDone(),
  }),
  getters: {
    step: (s): Step | null => s.tour?.steps[s.index] ?? null,
    active: (s) => !!s.tour,
  },
  actions: {
    async start(id: string, mode: Mode) {
      const tour = TOURS.find((t) => t.id === id);
      if (!tour || this.preparing) return;
      if (this.tour) await this.end(false);
      this.preparing = true;
      this.error = "";
      try {
        const world = await post<World>("/api/guide/sandbox");
        useSession().putWorld(world);
        Object.assign(this, { tour, mode, index: 0, sandbox: world, paused: false, finished: false, phone: null, missed: [] });
        before = storageKeys();
        lastUsed = readLastUsed();
        run += 1;
        void this.loop(run);
      } catch {
        this.error = "Couldn't make the sandbox. Try again in a moment.";
      } finally {
        this.preparing = false;
      }
    },

    /** End the walkthrough: the sandbox goes, with everything it left on this device, and the Guide page opens. */
    async end(back = true) {
      run += 1;
      const slug = this.sandbox?.slug;
      if (this.finished && this.tour) {
        this.done = { ...this.done, [this.tour.id]: new Date().toISOString() };
        try {
          localStorage.setItem(DONE_KEY, JSON.stringify(this.done));
        } catch {
          /* storage unavailable: progress isn't remembered */
        }
      }
      Object.assign(this, { tour: null, sandbox: null, phone: null, target: null, pointer: null, finished: false });
      if (back) await router.push({ name: "guide" });
      if (slug) {
        useSession().dropWorld(slug);
        forgetSandbox(slug, before);
        writeLastUsed(lastUsed.world === slug ? {} : lastUsed);
        await del("/api/guide/sandbox").catch(() => undefined);
      }
    },

    /** Remove a sandbox left behind (a tab closed mid-walkthrough), from the Guide page. */
    async clear() {
      for (const w of useSession().worlds.filter((x) => x.sandbox)) {
        useSession().dropWorld(w.slug);
        if (readLastUsed().world === w.slug) writeLastUsed({});
      }
      await del("/api/guide/sandbox").catch(() => undefined);
    },

    pause() {
      this.paused = !this.paused;
    },
    /** On to the next step: watched, without waiting; tried, doing this one for the writer. */
    next() {
      advance?.("next");
    },

    doc(): Document | null {
      if (this.step?.in !== "phone") return document;
      const frame = document.querySelector<HTMLIFrameElement>("[data-testid=guide-phone-frame]");
      return frame?.contentDocument ?? null;
    },

    async loop(me: number) {
      const stopped = () => me !== run;
      while (!stopped() && this.tour && this.index < this.tour.steps.length) {
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
        this.finished = true;
        this.target = null;
        this.pointer = null;
      }
    },

    async play(step: Step, stopped: () => boolean) {
      const w = this.sandbox!.slug;
      this.target = null;
      if (step.phone !== undefined) this.phone = step.phone ? step.phone.replace("{w}", w) : null;
      if (step.go) await router.push(step.go.replace("{w}", w));
      const doc = () => this.doc();
      const el = step.target ? await waitFor(doc, step.target, 15_000, stopped) : null;
      if (stopped()) return;
      this.target = el;
      if (step.target && !el) this.missed.push(`${this.index + 1}: ${step.target.css} ${step.target.text ?? ""}`.trim());
      if (el) el.scrollIntoView({ block: "nearest", inline: "nearest" });

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
        await perform(el!, step.act!, { slow: this.mode === "watch", stopped });
      }
      if (step.wait && (acting || how === "did") && !(await waitFor(doc, step.wait, 15_000, stopped)) && !stopped()) {
        this.missed.push(`${this.index + 1}: waited for ${step.wait.css} ${step.wait.text ?? ""}`.trim());
      }
      await sleep(how === "did" ? 300 : 150);
    },

    /** Watched: the caption's time on screen, held while paused. */
    async linger(step: Step, stopped: () => boolean) {
      const ms = step.read ?? Math.min(9000, 1600 + step.say.length * 38);
      let left = ms;
      while (left > 0 && !stopped()) {
        await sleep(100);
        if (!this.paused) left -= 100;
      }
    },

    /** Move the fake pointer onto `el` and press, so a watched click can be followed. */
    async pointAt(el: HTMLElement, stopped: () => boolean) {
      const r = el.getBoundingClientRect();
      const off = this.step?.in === "phone" ? document.querySelector("[data-testid=guide-phone-frame]")!.getBoundingClientRect() : { left: 0, top: 0 };
      const x = off.left + r.left + Math.min(r.width / 2, 40);
      const y = off.top + r.top + Math.min(r.height / 2, 14);
      if (this.mode !== "watch") return;
      this.pointer = { x, y, pressed: false };
      await sleep(650);
      if (stopped()) return;
      this.pointer = { x, y, pressed: true };
      await sleep(180);
      this.pointer = { x, y, pressed: false };
    },
  },
});

// outside the store: these never need to be reactive
let run = 0;
let advance: ((how: "time" | "next" | "did") => void) | null = null;
let before = new Set<string>();
let lastUsed: { world?: string; project?: string } = {};

