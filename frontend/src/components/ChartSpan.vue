<script setup lang="ts">
import { computed, ref, toRef, watch } from "vue";
import { useRouter } from "vue-router";

import { useSession } from "../stores/session";
import { useCards } from "../world/cards";
import { changesBetween, type ChartState } from "../world/chart";
import type { At } from "../world/time";
import { useChart } from "../world/usechart";
import { timeText, unitOf } from "../world/when";
import ChartCanvas from "./ChartCanvas.vue";

// The chart following the Timeline's brushed span (docs/SPEC.md §13.7.5): the state at the span's end, the places
// whose controlling faction, container or borders were different at its start outlined, and a list of what changed
// when, in happened order. A scrubber stops at each change, moving "as of" there (arrow keys step), and the chart eases
// between the states. Without a span: the latest state, or the chart's own "as of". Nothing is stored.
const props = withDefaults(defineProps<{ world: string; from: number | null; to: number | null; standings?: Set<string>; fallback?: At | null; height?: number; editable?: boolean }>(), {
  standings: () => new Set(["canon", "planned"]),
  fallback: null,
  height: 420,
  editable: true,
});
const router = useRouter();
const session = useSession();
const cards = useCards();
const chart = useChart(toRef(props, "world"));
const unit = computed(() => unitOf(session.world(props.world)));
const name = (id: string) => cards.byId.get(id)?.name ?? "?";

interface Stop {
  at: At;
  t: number;
  when: string;
}
/** the span's start, each point inside it where a "controls", "inside" or "borders" relationship starts or ends, and
 * its end */
const stops = computed<Stop[]>(() => {
  const g = chart.graph.value;
  const { from, to } = props;
  if (!g || from === null || to === null) return [];
  const node = new Map(g.nodes.map((n) => [n.id, n]));
  const chapters = new Map(cards.timeline.map((c) => [c.id, c]));
  const relevant = g.edges.filter((e) => {
    const a = node.get(e.a)?.kind;
    const b = node.get(e.b)?.kind;
    if (b !== "place" || (a !== "place" && a !== "faction")) return false;
    return a === "faction" ? /^controls$/i.test(e.label.trim()) : /^(inside|in|part of|within|borders)$/i.test(e.label.trim()) || /^contains$/i.test((e.reverse_label ?? "").trim());
  });
  // the clock's places with a set time, in order, to find the chapter after an "until"
  const placed = cards.timeline.filter((c) => c.clock != null && c.set_time != null && !c.early).sort((a, b) => a.clock! - b.clock!);
  const out = new Map<string, Stop>();
  const add = (s: Stop) => {
    if (s.t > from && s.t <= to) out.set(typeof s.at === "number" ? `c${s.at}` : `t${s.t}`, s);
  };
  // a bound holds at its own point ("until year 300" still holds in year 300), so each stop is read just after it:
  // a time a hair later, a chapter "until" at the chapter after it
  for (const e of relevant) {
    for (const side of ["from", "until"] as const) {
      const t = side === "from" ? e.from_time : e.until_time;
      const ch = side === "from" ? e.from_chapter_id : e.until_chapter_id;
      if (t != null) add({ at: { time: t + 1e-6 }, t, when: timeText({ time_at: t, time_approx: side === "from" ? e.from_approx : e.until_approx }, unit.value) });
      else if (ch) {
        const c = chapters.get(ch);
        if (!c || c.clock == null || c.set_time == null || c.early) continue;
        if (side === "from") add({ at: c.clock, t: c.set_time, when: `chapter ${c.index + 1}` });
        else {
          const next = placed.find((x) => x.clock! > c.clock!);
          if (next) add({ at: next.clock!, t: next.set_time!, when: `chapter ${c.index + 1}` });
        }
      }
    }
  }
  // in happened order: a time just before the chapters set at it
  const inside = [...out.values()].sort((x, y) => x.t - y.t || (typeof x.at === "number" ? 1 : 0) - (typeof y.at === "number" ? 1 : 0) || (typeof x.at === "number" && typeof y.at === "number" ? x.at - y.at : 0));
  const end: Stop = { at: { time: to }, t: to, when: timeText({ time_at: to }, unit.value) };
  const last = inside[inside.length - 1];
  return [{ at: { time: from }, t: from, when: timeText({ time_at: from }, unit.value) }, ...inside, ...(last && last.t === to ? [] : [end])];
});
const states = computed(() => stops.value.map((s) => chart.stateAt(s.at, null, props.standings)));
const step = ref(0);
watch(stops, (s) => (step.value = Math.max(0, s.length - 1)), { immediate: true });
const following = computed(() => stops.value.length > 0);
const shown = computed<ChartState | null>(() => (following.value ? (states.value[step.value] ?? null) : chart.stateAt(props.fallback, null, props.standings)));
const layout = computed(() => (shown.value ? chart.layoutOf(shown.value) : null));
/** what changed across the span, in happened order */
const changes = computed(() => {
  const out: { key: string; place: string; text: string; when: string; step: number }[] = [];
  for (let i = 1; i < states.value.length; i++) {
    const a = states.value[i - 1];
    const b = states.value[i];
    if (!a || !b) continue;
    for (const c of changesBetween(a, b, name)) for (const p of c.parts) out.push({ key: `${i}|${c.place}|${p}`, place: c.place, text: `${name(c.place)} · ${p}`, when: stops.value[i]!.when, step: i });
  }
  return out;
});
const outlined = computed(() => {
  const a = states.value[0];
  const b = shown.value;
  if (!following.value || !a || !b) return new Set<string>();
  return new Set(changesBetween(a, b, name).map((c) => c.place));
});
const point = computed(() => {
  const s = following.value ? stops.value[step.value] : null;
  if (s) return typeof s.at === "number" ? (cards.timeline.find((c) => c.clock === s.at)?.id ?? null) : { time: s.t };
  const f = props.fallback;
  return f === null ? null : typeof f === "number" ? (cards.timeline.find((c) => c.clock === f)?.id ?? null) : "time" in f ? { time: f.time } : null;
});
const open = (id: string) => void router.push({ name: "entity", params: { world: props.world, id } });
const pin = (place: string, container: string | null, x: number, y: number) => void chart.setPin(place, container, x, y);
</script>

<template>
  <div class="chart-span" data-testid="chart-span">
    <div v-if="following" class="chart-scrub">
      <input v-model.number="step" type="range" min="0" :max="stops.length - 1" step="1" class="grow" aria-label="Step through the span" data-testid="chart-scrubber" />
      <span class="small" data-testid="chart-scrub-at">as of {{ stops[step]?.when }}</span>
    </div>
    <ChartCanvas :state="shown" :layout="layout" :point="point" :outlined="outlined" :height="height" :editable="editable" @open="open" @pin="pin" />
    <ul v-if="following && changes.length" class="plain-list chart-changes small" data-testid="chart-changes">
      <li v-for="c in changes" :key="c.key" :class="{ ahead: c.step > step }">
        <button type="button" class="linkish" @click="step = c.step">{{ c.text }} · {{ c.when }}</button>
      </li>
    </ul>
    <p v-else-if="following" class="muted small">Nothing on the chart changes across this span.</p>
  </div>
</template>
