<script setup lang="ts">
import { computed, ref } from "vue";

import type { Span, StoryChapter } from "../types";
import { spanText } from "../world/time";
import { parseTime, timeFormat, timeText, type Unit } from "../world/when";

// When a fact or relationship holds: "always" until set, then "from Storm", "year 0 – Storm", "outside time"… Each side
// is a chapter (with its time) or a time (a number and "about"), never both (docs/SPEC.md §13.1.5); outside time has
// no bounds at all (§13.1.8). Click to change.
const props = withDefaults(defineProps<{ span: Span; timeline: StoryChapter[]; unit?: Unit }>(), { unit: () => ({ unit: "year", units: "years" }) });
const emit = defineEmits<{ save: [span: Span] }>();

const editing = ref(false);
const from = ref("");
const until = ref("");
const fromTime = ref("");
const untilTime = ref("");
const fromApprox = ref(false);
const untilApprox = ref(false);
const outside = ref(false);
const titles = computed(() => new Map(props.timeline.map((c) => [c.id, c.title])));
const text = computed(() => spanText(props.span, (id) => titles.value.get(id), timeFormat(props.unit)));
const projects = computed(() => {
  const out: { name: string; chapters: StoryChapter[] }[] = [];
  for (const c of props.timeline) {
    const last = out[out.length - 1];
    if (last?.name === c.project_name) last.chapters.push(c);
    else out.push({ name: c.project_name, chapters: [c] });
  }
  return out;
});
const optionText = (c: StoryChapter) => {
  const t = c.outside_time ? "outside time" : timeText(c.time_at != null ? c : { time_at: c.set_time ?? null, time_approx: c.set_approx }, props.unit);
  return t ? `${c.title} — ${t}` : c.title;
};
// "From" must come before "until" on the clock: chapters by their place, a time against a chapter's set time
const backwards = computed(() => {
  if (outside.value) return false;
  const place = (id: string) => props.timeline.find((c) => c.id === id);
  const point = (side: "from" | "until") => {
    const sel = side === "from" ? from.value : until.value;
    if (sel === "time") return { t: parseTime(side === "from" ? fromTime.value : untilTime.value), p: null as number | null };
    if (!sel) return null;
    const c = place(sel);
    return c ? { t: c.early ? null : (c.set_time ?? null), p: c.clock === undefined ? c.index : (c.clock ?? null) } : null;
  };
  const a = point("from");
  const b = point("until");
  if (!a || !b) return false;
  if (a.p !== null && b.p !== null) return a.p > b.p;
  return a.t !== null && b.t !== null && a.t > b.t;
});
const badTime = computed(() => (from.value === "time" && parseTime(fromTime.value) === null) || (until.value === "time" && parseTime(untilTime.value) === null));

function start() {
  from.value = props.span.from_time != null ? "time" : (props.span.from_chapter_id ?? "");
  until.value = props.span.until_time != null ? "time" : (props.span.until_chapter_id ?? "");
  fromTime.value = props.span.from_time != null ? String(props.span.from_time) : "";
  untilTime.value = props.span.until_time != null ? String(props.span.until_time) : "";
  fromApprox.value = !!props.span.from_approx;
  untilApprox.value = !!props.span.until_approx;
  outside.value = !!props.span.outside_time;
  editing.value = true;
}
function save() {
  editing.value = false;
  if (outside.value) {
    emit("save", { from_chapter_id: null, until_chapter_id: null, from_time: null, until_time: null, outside_time: true });
    return;
  }
  const side = (sel: string, t: string, approx: boolean) =>
    sel === "time" ? { chapter: null, time: parseTime(t), approx } : { chapter: sel || null, time: null, approx: false };
  const f = side(from.value, fromTime.value, fromApprox.value);
  const u = side(until.value, untilTime.value, untilApprox.value);
  emit("save", {
    from_chapter_id: f.chapter,
    from_time: f.time,
    from_approx: f.approx,
    until_chapter_id: u.chapter,
    until_time: u.time,
    until_approx: u.approx,
    outside_time: false,
  });
}
</script>

<template>
  <span v-if="!editing" class="span-text" :class="{ always: !text, outside: props.span.outside_time }">
    <button type="button" class="linkish small" :title="props.timeline.length ? 'When it holds' : 'Add chapters, or use a time'" @click="start">
      {{ text || "always" }}
    </button>
  </span>
  <form v-else class="span-form" @submit.prevent="save" @keydown.esc.prevent="editing = false">
    <template v-if="!outside">
      <label class="small muted">from
        <select v-model="from" class="filter" aria-label="From chapter">
          <option value="">the start</option>
          <optgroup v-for="p in projects" :key="p.name" :label="p.name">
            <option v-for="c in p.chapters" :key="c.id" :value="c.id">{{ optionText(c) }}</option>
          </optgroup>
          <option value="time">A time…</option>
        </select>
      </label>
      <template v-if="from === 'time'">
        <input v-model="fromTime" class="filter time-num" inputmode="decimal" aria-label="From time" :placeholder="props.unit.unit" />
        <label class="small check"><input v-model="fromApprox" type="checkbox" aria-label="From about" /> about</label>
      </template>
      <label class="small muted">until
        <select v-model="until" class="filter" aria-label="Until chapter">
          <option value="">the end</option>
          <optgroup v-for="p in projects" :key="p.name" :label="p.name">
            <option v-for="c in p.chapters" :key="c.id" :value="c.id">{{ optionText(c) }}</option>
          </optgroup>
          <option value="time">A time…</option>
        </select>
      </label>
      <template v-if="until === 'time'">
        <input v-model="untilTime" class="filter time-num" inputmode="decimal" aria-label="Until time" :placeholder="props.unit.unit" />
        <label class="small check"><input v-model="untilApprox" type="checkbox" aria-label="Until about" /> about</label>
      </template>
    </template>
    <label class="small check" title="At no point on the world's axis: a plane beyond the world, a myth, a vision"><input v-model="outside" type="checkbox" aria-label="Outside time" /> outside time</label>
    <button class="btn btn-sm btn-primary" type="submit" :disabled="backwards || badTime" :title="backwards ? '“From” comes after “until”' : ''">Set</button>
    <button class="btn btn-sm" type="button" @click="editing = false">Cancel</button>
  </form>
</template>
