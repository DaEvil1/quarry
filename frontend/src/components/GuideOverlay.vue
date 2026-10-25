<script setup lang="ts">
// The Guide's layer over the page while a walkthrough runs (docs/SPEC.md §15): a ring round what the step is about,
// a pointer that moves before a watched click, the caption in a corner where it covers no prose, and the phone when a
// step happens on one. It never takes focus and lets every click through to the page.
import { computed, onBeforeUnmount, ref, watch } from "vue";

import { hint } from "../guide/engine";
import { useGuide } from "../stores/guide";

const guide = useGuide();
const ring = ref<{ left: number; top: number; width: number; height: number } | null>(null);
const frame = ref<HTMLIFrameElement | null>(null);

let raf = 0;
function track() {
  const el = guide.target;
  if (el && el.isConnected) {
    const r = el.getBoundingClientRect();
    const off = guide.step?.in === "phone" && frame.value ? frame.value.getBoundingClientRect() : { left: 0, top: 0 };
    ring.value = { left: off.left + r.left - 4, top: off.top + r.top - 4, width: r.width + 8, height: r.height + 8 };
  } else {
    ring.value = null;
  }
  raf = requestAnimationFrame(track);
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
</script>

<template>
  <div v-if="guide.active" class="guide-layer" data-testid="guide">

    <div v-if="guide.phone" class="guide-phone" data-testid="guide-phone">
      <div class="guide-phone-notch" />
      <iframe ref="frame" :src="guide.phone" title="Quarry on a phone" data-testid="guide-phone-frame" />
    </div>

    <div v-if="ring" class="guide-ring" :style="{ left: `${ring.left}px`, top: `${ring.top}px`, width: `${ring.width}px`, height: `${ring.height}px` }" />
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
    <aside class="guide-card" :class="{ left: !!guide.phone }" role="status" aria-live="polite">
      <div class="guide-card-head">
        <span class="pill accent">Sandbox</span>
        <strong class="grow">{{ guide.tour?.title }}</strong>
        <span class="muted small">{{ position }}</span>
      </div>
      <template v-if="!guide.finished">
        <p class="guide-say">{{ guide.step?.say }}</p>
        <p v-if="yourTurn" class="guide-turn small">{{ yourTurn }}</p>
      </template>
      <template v-else>
        <p class="guide-say" data-testid="guide-finished">
          That's the walkthrough. Look around the sandbox as long as you like; ending it deletes the sandbox and
          everything done in it.
        </p>
        <p v-if="guide.missed.length" class="small guide-missed" data-testid="guide-missed">
          Some steps couldn't find their place (the app has changed since this walkthrough was written):
          {{ guide.missed.join("; ") }}
        </p>
      </template>
      <div class="actions">
        <button v-if="guide.mode === 'watch' && !guide.finished" type="button" class="btn btn-sm" data-testid="guide-pause" @click="guide.pause()">
          {{ guide.paused ? "Play" : "Pause" }}
        </button>
        <button v-if="!guide.finished" type="button" class="btn btn-sm btn-primary" data-testid="guide-next" @click="guide.next()">{{ nextLabel }}</button>
        <span class="spacer" />
        <button type="button" class="btn btn-sm" data-testid="guide-end" @click="guide.end()">End</button>
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
  box-shadow: 0 0 0 9999px rgb(0 0 0 / 0.18);
  transition: left 0.25s, top 0.25s, width 0.25s, height 0.25s;
}
.guide-pointer {
  position: fixed;
  transition: left 0.55s ease-in-out, top 0.55s ease-in-out, transform 0.1s;
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
