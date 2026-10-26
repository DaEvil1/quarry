<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";

import { pictureUrl } from "../pictures";
import { useViewer } from "../stores/viewer";

// The full view (docs/SPEC.md §17.2): the view copy as large as the window allows, its caption and name, Open full size
// (the full file, in a new tab) and, among several, ‹ › (the arrow keys, or a swipe on the phone). Esc closes it.
const viewer = useViewer();
const box = ref<HTMLElement | null>(null);
let lastFocus: Element | null = null;

function onKey(e: KeyboardEvent) {
  if (!viewer.open) return;
  if (e.key === "Escape") viewer.close();
  else if (e.key === "ArrowRight") viewer.step(1);
  else if (e.key === "ArrowLeft") viewer.step(-1);
  else return;
  e.preventDefault();
  e.stopPropagation();
}
watch(
  () => viewer.open,
  async (open) => {
    if (open) {
      lastFocus = document.activeElement;
      window.addEventListener("keydown", onKey, true);
      await nextTick();
      box.value?.focus();
    } else {
      window.removeEventListener("keydown", onKey, true);
      (lastFocus as HTMLElement | null)?.focus?.();
    }
  },
);
onBeforeUnmount(() => window.removeEventListener("keydown", onKey, true));

let touchX: number | null = null;
const touchStart = (e: TouchEvent) => (touchX = e.touches[0]?.clientX ?? null);
function touchEnd(e: TouchEvent) {
  const x = e.changedTouches[0]?.clientX;
  if (touchX !== null && x !== undefined && Math.abs(x - touchX) > 50) viewer.step(x < touchX ? 1 : -1);
  touchX = null;
}
</script>

<template>
  <div v-if="viewer.current" class="picture-viewer" role="dialog" aria-modal="true" :aria-label="viewer.current.caption || viewer.current.name" data-testid="picture-viewer" @click.self="viewer.close()">
    <div ref="box" class="pv-frame" tabindex="-1" @touchstart.passive="touchStart" @touchend.passive="touchEnd">
      <img :key="viewer.current.id" class="pv-img" :src="pictureUrl(viewer.current.id, 'view')" :alt="viewer.current.caption || viewer.current.name" data-testid="viewer-img" :data-picture="viewer.current.id" />
      <div class="pv-foot">
        <span class="grow">
          <span v-if="viewer.current.caption" class="pv-caption" data-testid="viewer-caption">{{ viewer.current.caption }}</span>
          <span class="muted small"> {{ viewer.current.name }}</span>
          <span v-if="viewer.items.length > 1" class="muted small"> · {{ viewer.index + 1 }} of {{ viewer.items.length }}</span>
        </span>
        <a class="btn btn-sm" :href="pictureUrl(viewer.current.id, 'full')" target="_blank" rel="noopener">Open full size</a>
        <button type="button" class="btn btn-sm" aria-label="Close" data-testid="viewer-close" @click="viewer.close()">×</button>
      </div>
    </div>
    <template v-if="viewer.items.length > 1">
      <button type="button" class="pv-step prev" aria-label="Previous picture" data-testid="viewer-prev" @click="viewer.step(-1)">‹</button>
      <button type="button" class="pv-step next" aria-label="Next picture" data-testid="viewer-next" @click="viewer.step(1)">›</button>
    </template>
  </div>
</template>
