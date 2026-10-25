<script setup lang="ts">
// The Guide's layer over the page while a walkthrough runs (docs/SPEC.md §15): a ring round what the step is about,
// a pointer that moves before a watched click, the caption beside what it points at (or in a corner when nothing
// beside it will do), a faint line from one to the other when they are apart, and the phone when a step happens on
// one. It never takes focus (its buttons don't either, so a field being typed in stays open) and lets every other
// click through to the page.
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { hint } from "../guide/engine";
import { connector, placeCaption, type Box, type Placement } from "../guide/place";
import { SPEEDS, useGuide } from "../stores/guide";

const guide = useGuide();
const ring = ref<Box | null>(null);
const frame = ref<HTMLIFrameElement | null>(null);
const card = ref<HTMLElement | null>(null);
/** where the caption is placed beside the target; null: its corner (no target, the phone frame, a phone) */
const placed = ref<Placement | null>(null);
const line = ref<{ x1: number; y1: number; x2: number; y2: number } | null>(null);

// on a phone the caption stays docked at the bottom, with the line pointing up to the target
const phoneQuery = typeof window !== "undefined" ? window.matchMedia("(max-width: 767px)") : null;
const narrow = ref(phoneQuery?.matches ?? false);
const onNarrow = () => (narrow.value = phoneQuery?.matches ?? false);
onMounted(() => phoneQuery?.addEventListener("change", onNarrow));
onBeforeUnmount(() => phoneQuery?.removeEventListener("change", onNarrow));

/** Is there text at this point of the page (not the Guide's own layer)? The caption would rather not cover it. */
function isText(x: number, y: number): boolean {
  const el = document.elementsFromPoint(x, y).find((e) => !e.closest("[data-testid=guide]"));
  if (!el || el === document.body || el === document.documentElement) return false;
  if (el.closest(".cm-line, p, li, td, th, h1, h2, h3, h4, label, a, button")) return true;
  return [...el.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && !!n.textContent?.trim());
}

const boxOf = (r: DOMRect | Box): Box => ({ left: r.left, top: r.top, width: r.width, height: r.height });

// the ring follows its target every frame; the caption is placed again when the ring, the caption's size or the
// window changes, at most every 80 ms while it keeps changing (a scroll), and once more when it stops
let raf = 0;
let lastKey = "";
let lastPlaced = 0;
let pending = false;
function track() {
  const el = guide.target;
  if (el && el.isConnected && guide.shown) {
    const r = el.getBoundingClientRect();
    const off = guide.step?.in === "phone" && frame.value ? frame.value.getBoundingClientRect() : { left: 0, top: 0 };
    const g = { left: off.left + r.left - 4, top: off.top + r.top - 4, width: r.width + 8, height: r.height + 8 };
    ring.value = g;
    const c = card.value;
    if (c) {
      const key = [g.left, g.top, g.width, g.height, c.offsetWidth, c.offsetHeight, window.innerWidth, window.innerHeight, guide.index]
        .map((v) => Math.round(v))
        .join(",");
      if (key !== lastKey) {
        lastKey = key;
        pending = true;
      }
      const now = performance.now();
      if (pending && now - lastPlaced > 80) {
        pending = false;
        lastPlaced = now;
        place(c, g);
      }
      line.value = connector(boxOf(c.getBoundingClientRect()), g);
    }
  } else {
    ring.value = null;
    placed.value = null;
    line.value = null;
    lastKey = "";
  }
  raf = requestAnimationFrame(track);
}
function place(c: HTMLElement, target: Box) {
  if (narrow.value || guide.phone) {
    placed.value = null;
    return;
  }
  // kept clear: what the next step uses, and the nav (a caption over it reads as part of the nav)
  const avoid = [guide.upcoming?.isConnected ? guide.upcoming : null, document.querySelector<HTMLElement>("aside.nav")]
    .map((el) => (el ? boxOf(el.getBoundingClientRect()) : null))
    .filter((b): b is Box => !!b && b.width > 0 && b.height > 0);
  placed.value = placeCaption({
    target,
    card: { width: c.offsetWidth, height: c.offsetHeight },
    view: { width: window.innerWidth, height: window.innerHeight },
    avoid,
    isText,
  });
}
watch(
  () => guide.active,
  (on) => {
    cancelAnimationFrame(raf);
    if (on) raf = requestAnimationFrame(track);
    else ring.value = null;
  },
  { immediate: true },
);
onBeforeUnmount(() => cancelAnimationFrame(raf));

const position = computed(() => (guide.finished ? "done" : `${guide.index + 1} of ${guide.tour?.steps.length ?? 0}`));
const yourTurn = computed(() => (guide.mode === "try" && guide.step?.act ? hint(guide.step.act) : ""));
const nextLabel = computed(() => (guide.mode === "try" && guide.step?.act ? "Do it for me" : "Next"));
const speedLabel = (v: number) => `${v}×`;
/** the page dimmed a little around the ring: while watching by default, or always, or never (the Guide page says) */
const dim = computed(() => guide.spotlight === "always" || (guide.spotlight === "watching" && guide.mode === "watch"));
const cardStyle = computed(() =>
  placed.value ? { left: `${placed.value.left}px`, top: `${placed.value.top}px`, right: "auto", bottom: "auto" } : {},
);
</script>

<template>
  <div v-if="guide.active" class="guide-layer" data-testid="guide" :style="{ '--guide-speed': guide.speed }">

    <div v-if="guide.phone" class="guide-phone" data-testid="guide-phone">
      <div class="guide-phone-notch" />
      <iframe ref="frame" :src="guide.phone" title="Quarry on a phone" data-testid="guide-phone-frame" />
    </div>

    <div
      v-if="ring"
      class="guide-ring"
      :class="{ dim }"
      data-testid="guide-ring"
      :style="{ left: `${ring.left}px`, top: `${ring.top}px`, width: `${ring.width}px`, height: `${ring.height}px` }"
    />
    <svg v-if="line" class="guide-line" aria-hidden="true" data-testid="guide-line">
      <line :x1="line.x1" :y1="line.y1" :x2="line.x2" :y2="line.y2" />
      <circle :cx="line.x2" :cy="line.y2" r="3" />
    </svg>
    <svg
      v-if="guide.pointer"
      class="guide-pointer"
      :class="{ pressed: guide.pointer.pressed }"
      :style="{ left: `${guide.pointer.x}px`, top: `${guide.pointer.y}px` }"
      width="22"
      height="22"
      viewBox="0 0 22 22"
      aria-hidden="true"
    >
      <path d="M3 2l15 8.5-6.5 1.6L8.6 19z" />
    </svg>
    <aside
      ref="card"
      class="guide-card"
      :class="{ left: !!guide.phone && !placed, placed: !!placed, waiting: !guide.shown && !guide.finished }"
      :style="cardStyle"
      :data-side="placed?.side ?? (narrow ? 'docked' : 'corner')"
      data-testid="guide-card"
      role="status"
      aria-live="polite"
    >
      <div class="guide-card-head">
        <span class="pill accent">Sandbox</span>
        <strong class="grow">{{ guide.tour?.title }}</strong>
        <span class="muted small">{{ position }}</span>
        <button
          type="button"
          class="icon-btn"
          @mousedown.prevent
          :aria-label="guide.folded ? 'Show the caption' : 'Fold the caption'"
          data-testid="guide-fold"
          @click="guide.folded = !guide.folded"
        >
          {{ guide.folded ? "▴" : "▾" }}
        </button>
      </div>
      <template v-if="guide.folded" />
      <template v-else-if="!guide.finished">
        <p class="guide-say">{{ guide.step?.say }}</p>
        <p v-if="yourTurn" class="guide-turn small">{{ yourTurn }}</p>
      </template>
      <template v-else>
        <p class="guide-say" data-testid="guide-finished">
          That's the walkthrough. The sandbox stays for you to look around in, until the next walkthrough replaces it
          or you delete it from the Guide page.
        </p>
        <p v-if="guide.missed.length" class="small guide-missed" data-testid="guide-missed">
          Some steps couldn't find their place (the app has changed since this walkthrough was written):
          {{ guide.missed.join("; ") }}
        </p>
      </template>
      <div v-if="!guide.folded" class="actions">
        <button v-if="guide.mode === 'watch' && !guide.finished" type="button" class="btn btn-sm" data-testid="guide-pause" @mousedown.prevent @click="guide.pause()">
          {{ guide.paused ? "Play" : "Pause" }}
        </button>
        <button v-if="!guide.finished" type="button" class="btn btn-sm btn-primary" data-testid="guide-next" @mousedown.prevent @click="guide.next()">{{ nextLabel }}</button>
        <span class="spacer" />
        <select
          v-if="guide.mode === 'watch' && !guide.finished"
          class="filter guide-speed"
          aria-label="Speed"
          data-testid="guide-speed"
          :value="guide.speed"
          @change="guide.setSpeed(Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="v in SPEEDS" :key="v" :value="v">{{ speedLabel(v) }}</option>
        </select>
        <button type="button" class="btn btn-sm" data-testid="guide-end" @mousedown.prevent @click="guide.stop()">{{ guide.finished ? "Close" : "End" }}</button>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.guide-layer {
  position: fixed;
  inset: 0;
  z-index: 900;
  pointer-events: none;
}
.guide-ring {
  position: fixed;
  border: 2px solid var(--accent);
  border-radius: calc(var(--radius) + 2px);
  transition: left 0.25s, top 0.25s, width 0.25s, height 0.25s;
}
.guide-ring.dim {
  /* a soft spotlight: the page dimmed a little around what the step is about; clicks still go through */
  box-shadow: 0 0 0 9999px rgb(0 0 0 / 0.18);
  transition: left 0.25s, top 0.25s, width 0.25s, height 0.25s;
}
.guide-pointer {
  position: fixed;
  transition: left calc(0.55s / var(--guide-speed, 1)) ease-in-out, top calc(0.55s / var(--guide-speed, 1)) ease-in-out, transform 0.1s;
  filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.5));
}
.guide-pointer path {
  fill: var(--surface);
  stroke: var(--text);
  stroke-width: 1.4;
  stroke-linejoin: round;
}
.guide-pointer.pressed {
  transform: scale(0.82);
}
.guide-card {
  pointer-events: auto;
  position: fixed;
  right: 16px;
  bottom: calc(16px + env(safe-area-inset-bottom));
  width: min(360px, calc(100vw - 32px));
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 8px 28px rgb(0 0 0 / 0.28);
  padding: 12px 14px;
}
.guide-card.placed {
  transition: left 0.2s ease-out, top 0.2s ease-out, opacity 0.12s;
}
.guide-card.waiting {
  /* while the page scrolls the step's target into view */
  opacity: 0;
}
.guide-line {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.guide-line line {
  stroke: var(--accent);
  stroke-width: 1.5;
  stroke-opacity: 0.45;
  stroke-dasharray: 4 3;
}
.guide-line circle {
  fill: var(--accent);
  fill-opacity: 0.6;
}
@media (prefers-reduced-motion: reduce) {
  .guide-card.placed,
  .guide-ring {
    transition: none;
  }
}
.guide-speed {
  width: auto;
  padding: 2px 6px;
}
.guide-card.left {
  /* beside the phone, not over it */
  right: 438px;
}
.guide-card-head {
  display: flex;
  gap: 8px;
  align-items: center;
}
.guide-say {
  margin: 8px 0;
  line-height: 1.45;
}
.guide-missed {
  color: var(--warn);
}
.guide-turn {
  margin: 0 0 8px;
  color: var(--accent);
}
.guide-card .spacer {
  flex: 1;
}
.guide-phone {
  pointer-events: auto;
  position: fixed;
  right: 24px;
  top: 50%;
  transform: translateY(-50%);
  width: 390px;
  height: min(780px, calc(100vh - 40px));
  padding: 14px 10px;
  border-radius: 38px;
  background: #0b0d10;
  box-shadow: 0 0 0 2px #2a2f37, 0 18px 50px rgb(0 0 0 / 0.5);
}
.guide-phone-notch {
  position: absolute;
  top: 6px;
  left: 50%;
  width: 90px;
  height: 6px;
  margin-left: -45px;
  border-radius: 3px;
  background: #2a2f37;
}
.guide-phone iframe {
  width: 100%;
  height: 100%;
  border: 0;
  border-radius: 28px;
  background: var(--bg);
}
@media (max-width: 767px) {
  /* on a real phone the page already is the phone */
  .guide-phone {
    inset: 0;
    transform: none;
    width: auto;
    height: auto;
    padding: 0;
    border-radius: 0;
  }
  .guide-phone iframe {
    border-radius: 0;
  }
  .guide-card,
  .guide-card.left {
    left: 16px;
    right: 16px;
    width: auto;
    bottom: calc(var(--tabbar-h) + 12px);
  }
}
</style>
