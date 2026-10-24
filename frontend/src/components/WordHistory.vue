<script setup lang="ts">
import { computed, ref } from "vue";

import type { WordHistory } from "../manuscript";
import { RANGES, wordBars, type Bar, type Range } from "../wordhistory";

// Words written (bars up) and cut (fainter, below the line) per day, week or month, from the revisions. No goals,
// no streaks, no colour that says a day was good or bad: a day without writing is just empty.
const props = defineProps<{ history: WordHistory }>();
const range = ref<Range>("weeks");
const shown = computed(() => wordBars(props.history, range.value));
const top = computed(() => Math.max(1, ...shown.value.bars.map((b) => b.written)));
const bottom = computed(() => Math.max(1, ...shown.value.bars.map((b) => b.cut)));
// written gets most of the height; cut a smaller band below the line
const W = 560;
const UP = 70;
const DOWN = 30;
const step = computed(() => W / shown.value.bars.length);
const hover = ref<Bar | null>(null);
const n = (x: number) => x.toLocaleString();
</script>

<template>
  <section class="card" data-testid="word-history">
    <div class="card-head">
      <h2>Words</h2>
      <div class="tabs" role="tablist" aria-label="Range">
        <button v-for="r in RANGES" :key="r.value" type="button" role="tab" class="tab" :aria-selected="range === r.value" @click="range = r.value">{{ r.label }}</button>
      </div>
    </div>
    <svg class="word-chart" :viewBox="`0 0 ${W} ${UP + DOWN + 2}`" preserveAspectRatio="none" role="img"
      :aria-label="`${n(shown.written)} words written, ${n(shown.cut)} cut`" @mouseleave="hover = null">
      <line x1="0" :x2="W" :y1="UP" :y2="UP" class="word-axis" />
      <g v-for="(b, i) in shown.bars" :key="b.key" @mouseenter="hover = b" @focus="hover = b">
        <rect :x="i * step" y="0" :width="step" :height="UP + DOWN" class="word-hit" />
        <rect v-if="b.written" class="word-up" :x="i * step + step * 0.15" :width="step * 0.7"
          :y="UP - (b.written / top) * (UP - 2)" :height="(b.written / top) * (UP - 2)" />
        <rect v-if="b.cut" class="word-down" :x="i * step + step * 0.15" :width="step * 0.7"
          :y="UP + 1" :height="(b.cut / bottom) * (DOWN - 2)" />
      </g>
    </svg>
    <p class="small word-hover" data-testid="word-hover">
      <template v-if="hover">
        <strong>{{ hover.label }}</strong>: {{ n(hover.written) }} written, {{ n(hover.cut) }} cut<template v-if="hover.chapters.length"> · {{ hover.chapters.join(", ") }}</template>
      </template>
      <template v-else>&nbsp;</template>
    </p>
    <p class="small muted" data-testid="word-total">{{ n(shown.written) }} words written, {{ n(shown.cut) }} cut.</p>
  </section>
</template>
