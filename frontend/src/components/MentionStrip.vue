<script setup lang="ts">
import { computed, ref } from "vue";

import type { StoryChapter } from "../types";
import { mentionStrip, type StripCell } from "../world/strip";

// Where in the story an entry is named (docs/SPEC.md §12.1): a cell per current chapter, filled by how often, a bar
// under its point-of-view chapters, gaps bracketed below, and a line that sums it up. Resting on a cell (long-press on
// the phone) says which chapter and how often; clicking opens it.
const props = defineProps<{
  world: string;
  entityId: string;
  timeline: StoryChapter[];
  /** chapter id -> how often it names the entry */
  counts: Map<string, number>;
  asOf: number | null;
}>();

const strip = computed(() => mentionStrip(props.timeline, props.counts, props.entityId, props.asOf));
const several = computed(() => strip.value.rows.length > 1);
const inGap = (n: number) => strip.value.gaps.find((g) => g.from <= n && n <= g.to);
const tip = ref("");
const tell = (c: StripCell) =>
  `${c.n}. ${c.chapter.title}${several.value ? ` (${c.chapter.project_name})` : ""} · ${c.count ? `named ${c.count === 1 ? "once" : `${c.count} times`}` : "not named"}${c.pov ? " · point of view" : ""}`;

// a long press on a phone shows what resting on it shows with a mouse
let pressed = 0;
let longPress = false;
function down(e: PointerEvent, c: StripCell) {
  if (e.pointerType === "mouse") return;
  longPress = false;
  window.clearTimeout(pressed);
  pressed = window.setTimeout(() => {
    longPress = true;
    tip.value = tell(c);
  }, 450);
}
const up = () => window.clearTimeout(pressed);
function click(e: MouseEvent) {
  if (longPress) {
    e.preventDefault();
    longPress = false;
  }
}
</script>

<template>
  <section class="mention-strip" data-testid="mention-strip">
    <p class="small strip-line" data-testid="strip-line">{{ strip.line }}</p>
    <div v-for="row in strip.rows" :key="row.project" class="strip-row">
      <span v-if="several" class="strip-project small muted">{{ row.name }}</span>
      <div class="strip-cells">
        <RouterLink
          v-for="c in row.cells"
          :key="c.chapter.id"
          class="strip-cell"
          :class="[`s${c.step}`, { later: c.later, asof: c.asOf, gap: inGap(c.n) }]"
          :to="{ name: 'chapter', params: { world: props.world, id: c.chapter.id } }"
          :title="tell(c)"
          :aria-label="tell(c)"
          :data-n="c.n"
          :data-count="c.count"
          @mouseenter="tip = tell(c)"
          @mouseleave="tip = ''"
          @pointerdown="down($event, c)"
          @pointerup="up"
          @pointercancel="up"
          @click="click"
          @contextmenu.prevent
        >
          <span class="box" />
          <span class="pov" :class="{ on: c.pov }" />
          <span class="bracket">
            <span v-if="inGap(c.n)?.from === c.n" class="gap-label" data-testid="strip-gap">{{ inGap(c.n)!.length }} chapters</span>
          </span>
        </RouterLink>
      </div>
    </div>
    <p class="small muted strip-tip" aria-live="polite">{{ tip || " " }}</p>
  </section>
</template>
