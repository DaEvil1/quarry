<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import AsOfPicker from "../components/AsOfPicker.vue";
import ChartCanvas from "../components/ChartCanvas.vue";
import ChartSpan from "../components/ChartSpan.vue";
import UndoToast from "../components/UndoToast.vue";
import { useSession } from "../stores/session";
import { useCards } from "../world/cards";
import { DEPTHS, inside, shapeOf, SHAPE_WORDS, SHAPES, type Pin, type Shape } from "../world/chart";
import type { At } from "../world/time";
import { useChart } from "../world/usechart";
import { unitOf } from "../world/when";
import NotFoundView from "./NotFoundView.vue";

// The chart (docs/SPEC.md §13.7): a schematic map of the world's places, drawn from what is recorded. Filters (types,
// "down to", standing), "as of" and the place to centre on are in the address. Dragging a place pins it; Reset layout
// unpins everything, or everything inside one place, with Undo. With "Follow the Timeline" it follows the span last
// brushed there (§13.7.5).
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const unit = computed(() => unitOf(world.value));
const chart = useChart(worldSlug);
const setQuery = (q: Record<string, string | undefined>) => void router.replace({ query: { ...route.query, ...q } });
const list = (k: string) => (typeof route.query[k] === "string" && route.query[k] ? String(route.query[k]).split(",") : []);

// as of: a chapter or a time, or nothing (the end of the story)
const asOfId = computed(() => (typeof route.query.asof === "string" ? route.query.asof : ""));
const atTime = computed(() => {
  const n = typeof route.query.at === "string" ? Number(route.query.at) : NaN;
  return Number.isFinite(n) ? n : null;
});
const asOf = computed<At | null>(() => (atTime.value !== null ? { time: atTime.value } : asOfId.value ? (cards.pointOf(asOfId.value) ?? null) : null));
const point = computed(() => (atTime.value !== null ? { time: atTime.value } : asOfId.value || null));
// filters
const standings = computed(() => new Set(["canon", ...list("standings").filter((s) => s === "planned" || s === "rumour")]));
const standingsOn = (s: string) => standings.value.has(s);
function toggleStanding(s: string) {
  const next = new Set(list("standings"));
  if (next.has(s)) next.delete(s);
  else next.add(s);
  setQuery({ standings: [...next].join(",") || undefined });
}
const hidden = computed(() => new Set(list("hide")));
const downTo = computed(() => {
  const n = Number(route.query.depth);
  return n >= 1 && n <= 4 ? n : 4;
});
const focus = computed(() => (typeof route.query.focus === "string" ? route.query.focus : ""));

const state = computed(() => chart.stateAt(asOf.value, asOfId.value || null, standings.value));
const visible = (id: string) => {
  const p = state.value?.places.get(id);
  if (!p) return false;
  return p.level <= downTo.value && !hidden.value.has((p.type ?? "no type").toLowerCase());
};
const layout = computed(() => (state.value ? chart.layoutOf(state.value, visible) : null));
/** the type values in use, for showing or hiding each */
const typesInUse = computed(() => {
  const out = new Map<string, number>();
  for (const p of state.value?.places.values() ?? []) {
    const k = (p.type ?? "no type").toLowerCase();
    out.set(k, (out.get(k) ?? 0) + 1);
  }
  return [...out.entries()].sort((a, b) => a[0].localeCompare(b[0]));
});
function toggleType(t: string) {
  const next = new Set(hidden.value);
  if (next.has(t)) next.delete(t);
  else next.add(t);
  setQuery({ hide: [...next].join(",") || undefined });
}

// ---- pins, reset with Undo ----
const toast = ref<{ label: string; undo: (() => Promise<void>) | null } | null>(null);
const error = ref("");
async function pin(place: string, container: string | null, x: number, y: number) {
  try {
    await chart.setPin(place, container, x, y);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
const containers = computed(() => [...(state.value?.places.values() ?? [])].filter((p) => p.children.length).sort((a, b) => a.name.localeCompare(b.name)));
async function reset(container?: string) {
  try {
    const ids = container && state.value ? [container, ...inside(state.value, container)] : undefined;
    const removed: Pin[] = await chart.resetPins(ids);
    const where = container ? ` inside ${cards.byId.get(container)?.name ?? "it"}` : "";
    toast.value = { label: removed.length ? `Unpinned ${removed.length} ${removed.length === 1 ? "place" : "places"}${where}` : `Nothing was pinned${where}`, undo: removed.length ? () => chart.putBack(removed) : null };
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// ---- shapes for the world's own types ----
const showShapes = ref(false);
const ownTypes = computed(() => typesInUse.value.map(([t]) => t).filter((t) => t !== "no type" && (shapeOf([t], {}).shape === "none" || chart.chart.value.settings.shapes[t])));
async function setShape(type: string, shape: string) {
  const shapes = { ...chart.chart.value.settings.shapes };
  if (shape) shapes[type] = shape;
  else delete shapes[type];
  try {
    await chart.saveShapes(shapes);
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// ---- following the Timeline: the span last brushed there, kept on this device ----
const following = computed(() => route.query.follow === "1");
const span = ref<{ from: number; to: number } | null>(null);
const readSpan = () => {
  try {
    const s = JSON.parse(localStorage.getItem(`timeline-span:${worldSlug.value}`) ?? "null") as { from: number; to: number } | null;
    span.value = s && Number.isFinite(s.from) && Number.isFinite(s.to) ? s : null;
  } catch {
    span.value = null;
  }
};
const onStorage = (e: StorageEvent) => e.key === `timeline-span:${worldSlug.value}` && readSpan();
// the chart is as tall as the window leaves it below the tools (at least 420 px), so a wide screen shows it larger
const winH = ref(typeof window !== "undefined" ? window.innerHeight : 800);
const onResize = () => (winH.value = window.innerHeight);
const chartH = computed(() => Math.max(420, winH.value - 250));
onMounted(() => {
  readSpan();
  window.addEventListener("storage", onStorage);
  window.addEventListener("resize", onResize);
});
onBeforeUnmount(() => {
  window.removeEventListener("storage", onStorage);
  window.removeEventListener("resize", onResize);
});

const canvas = ref<InstanceType<typeof ChartCanvas> | null>(null);
const open = (id: string) => void router.push({ name: "entity", params: { world: worldSlug.value, id } });
const shapeWord = (s: Shape) => SHAPE_WORDS[s];
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Chart</h1>
      </div>
      <div class="actions">
        <button type="button" class="btn btn-sm" data-testid="chart-fit" @click="canvas?.fit()">Fit</button>
        <button type="button" class="btn btn-sm" data-testid="chart-reset" @click="reset()">Reset layout</button>
        <select class="filter" value="" aria-label="Reset inside a place" data-testid="chart-reset-inside" @change="(e) => { const v = (e.target as HTMLSelectElement).value; (e.target as HTMLSelectElement).value = ''; if (v) void reset(v); }">
          <option value="">Reset inside…</option>
          <option v-for="c in containers" :key="c.id" :value="c.id">Reset inside {{ c.name }}</option>
        </select>
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': showShapes }" data-testid="chart-shapes" @click="showShapes = !showShapes">Shapes…</button>
      </div>
    </div>
    <div v-if="error || chart.error.value" class="notice error" role="alert">{{ error || chart.error.value }}</div>

    <div class="toolbar chart-tools">
      <label class="chip static"><input type="checkbox" :checked="following" data-testid="chart-follow" @change="setQuery({ follow: following ? undefined : '1' })" /> Follow the Timeline</label>
      <AsOfPicker v-if="!following && (cards.timeline.length || cards.anyTime)" :timeline="cards.timeline" :unit="unit" :asof="asOfId" :at="atTime" :times="cards.timed || cards.anyTime" :era-of="cards.eraOf" testid="chart-as-of"
        @pick="(c) => setQuery({ asof: c.asof, at: c.at !== undefined ? String(c.at) : undefined })" />
      <label class="small muted">Down to
        <select class="filter" :value="downTo" data-testid="chart-depth" @change="setQuery({ depth: ($event.target as HTMLSelectElement).value === '4' ? undefined : ($event.target as HTMLSelectElement).value })">
          <option v-for="d in DEPTHS" :key="d.value" :value="d.value">{{ d.label }}</option>
        </select>
      </label>
      <span v-for="s in ['planned', 'rumour']" :key="s" class="chip static"><label><input type="checkbox" :checked="standingsOn(s)" :data-testid="`chart-standing-${s}`" @change="toggleStanding(s)" /> {{ s }}</label></span>
    </div>
    <div v-if="typesInUse.length" class="chart-types small">
      <span v-for="[t, n] in typesInUse" :key="t" class="chip static"><label><input type="checkbox" :checked="!hidden.has(t)" :data-testid="`chart-type-${t}`" @change="toggleType(t)" /> {{ t }} ({{ n }})</label></span>
    </div>

    <section v-if="showShapes" class="card chart-settings" data-testid="chart-settings">
      <h2 class="small muted">Shapes for this world's types</h2>
      <p v-if="!ownTypes.length" class="muted small">Every type in use has a shape already.</p>
      <ul class="rows">
        <li v-for="t in ownTypes" :key="t">
          <span class="grow">{{ t }}</span>
          <select class="filter" :value="chart.chart.value.settings.shapes[t] ?? ''" :aria-label="`The shape for ${t}`" @change="setShape(t, ($event.target as HTMLSelectElement).value)">
            <option value="">no shape (lighter)</option>
            <option v-for="s in SHAPES" :key="s" :value="s">{{ shapeWord(s) }}</option>
          </select>
        </li>
      </ul>
    </section>

    <template v-if="following">
      <p v-if="!span" class="notice small">Brush a span on the Timeline and the chart follows it here.</p>
      <ChartSpan :world="world.slug" :from="span?.from ?? null" :to="span?.to ?? null" :standings="standings" :height="chartH" />
    </template>
    <template v-else>
      <p v-if="chart.graph.value && !state?.places.size" class="empty">No places in the bible yet.</p>
      <ChartCanvas v-else ref="canvas" :state="state" :layout="layout" :point="point" :focus="focus" :height="chartH" @open="open" @pin="pin" />
      <p v-if="layout?.unplaced.length" class="small muted" data-testid="chart-unplaced">Couldn't place: {{ layout.unplaced.join(" · ") }}</p>
    </template>
    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" @dismiss="toast = null" />
  </template>
</template>
