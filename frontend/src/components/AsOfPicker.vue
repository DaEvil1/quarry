<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { StoryChapter } from "../types";
import { asOfLabel, parseTime, timeFormat, type Unit } from "../world/when";

// "As of" (docs/SPEC.md §13.1.6): the book's chapters per project in book order, each with its set time and mark
// (`14 · The Drowned Bell — tale, year −800`), and once anything has a time, "At a time…": a number. Kept in the
// address by the page: `?asof=<chapter>` or `?at=<number>`.
const props = withDefaults(defineProps<{ timeline: StoryChapter[]; unit: Unit; asof: string; at: number | null; times?: boolean; testid?: string; label?: string }>(), {
  times: false,
  testid: "as-of",
  label: "As of",
});
const emit = defineEmits<{ pick: [choice: { asof?: string; at?: number }] }>();

const groups = computed(() => {
  const out: { name: string; chapters: { c: StoryChapter; n: number }[] }[] = [];
  props.timeline.forEach((c, i) => {
    const last = out[out.length - 1];
    if (last?.name === c.project_name) last.chapters.push({ c, n: i + 1 });
    else out.push({ name: c.project_name, chapters: [{ c, n: i + 1 }] });
  });
  return out;
});
const typing = ref(false);
const draft = ref("");
watch(
  () => props.at,
  (a) => {
    typing.value = a !== null;
    draft.value = a !== null ? String(a) : "";
  },
  { immediate: true },
);
const value = computed(() => (props.at !== null || typing.value ? "@time" : props.asof));
function change(v: string) {
  if (v === "@time") {
    typing.value = true;
    return;
  }
  typing.value = false;
  emit("pick", { asof: v || undefined });
}
function setTime() {
  const t = parseTime(draft.value);
  if (t !== null) emit("pick", { at: t });
}
</script>

<template>
  <span class="as-of-pick">
    <label :for="`${props.testid}-select`" class="small muted">{{ props.label }}</label>
    <select :id="`${props.testid}-select`" class="filter" :value="value" :data-testid="props.testid" @change="change(($event.target as HTMLSelectElement).value)">
      <option value="">the whole story</option>
      <optgroup v-for="p in groups" :key="p.name" :label="p.name">
        <option v-for="x in p.chapters" :key="x.c.id" :value="x.c.id">{{ props.times ? asOfLabel(x.c, x.n, props.unit) : x.c.title }}</option>
      </optgroup>
      <option v-if="props.times" value="@time">At a time…</option>
    </select>
    <form v-if="typing" class="as-of-time" @submit.prevent="setTime">
      <input v-model="draft" class="filter time-num" inputmode="decimal" :aria-label="`${props.label} a time`" :placeholder="props.unit.unit" :data-testid="`${props.testid}-time`" />
      <button class="btn btn-sm" type="submit">Set</button>
      <span v-if="props.at !== null" class="muted small">{{ timeFormat(props.unit)(props.at) }}</span>
    </form>
  </span>
</template>
