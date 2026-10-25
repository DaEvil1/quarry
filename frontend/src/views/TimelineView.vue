<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get } from "../api";
import { updateEntity, getEntity } from "../bible";
import ChartSpan from "../components/ChartSpan.vue";
import EntityPicker from "../components/EntityPicker.vue";
import { chronology as getChronology, type Chronology } from "../history";
import { useSession } from "../stores/session";
import type { StoryChapter } from "../types";
import { useCards } from "../world/cards";
import { eraAt, type Era } from "../world/eras";
import type { GraphData } from "../world/graph";
import { hideCard, showCard } from "../world/hovercard";
import { arrowPath, causeLinks, linksOf } from "../world/causes";
import {
  buildLanes,
  buildModel,
  cluster,
  fitScale,
  foldAtFor,
  inSpan,
  makeAxis,
  placeLabels,
  scaleOfStep,
  stepOf,
  ticks,
  type Item,
  type Lane,
  type Mark,
  type MarkKind,
} from "../world/timeline";
import { numberText } from "../world/time";
import { fitText, textWidth } from "../world/textwidth";
import { parseTime, timeText, unitOf } from "../world/when";
import NotFoundView from "./NotFoundView.vue";

// The Timeline (docs/SPEC.md §13.2.2, the design brief in §13.2.6): one axis, to scale with empty stretches folded,
// eras as background bands in their colours, the events, the book, and a lane per chosen character, faction or era;
// a told view in book order; and History, the happened view cut off where the book begins. Wheel or pinch zooms around
// the pointer, dragging pans, dragging along the axis (or the overview) brushes a span. The model is worked out once
// per change of data, clusters once per zoom step, and only what is on screen is drawn.
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const unit = computed(() => unitOf(world.value));
const view = computed(() => (route.query.view === "told" ? "told" : route.query.view === "history" ? "history" : "happened"));
const setQuery = (q: Record<string, string | undefined>) => void router.replace({ query: { ...route.query, ...q } });
const list = (k: string) => (typeof route.query[k] === "string" && route.query[k] ? String(route.query[k]).split(",") : []);

// ---- data ----
const graph = shallowRef<GraphData | null>(null);
const chron = shallowRef<Chronology | null>(null);
const error = ref("");
async function load() {
  error.value = "";
  try {
    const w = encodeURIComponent(worldSlug.value);
    [graph.value, chron.value] = await Promise.all([get<GraphData>(`/api/worlds/${w}/graph`), getChronology(worldSlug.value)]);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(worldSlug, (w) => {
  void cards.load(w, true);
  void load();
}, { immediate: true });

// ---- filters, kept in the address; the last used remembered per world on this device ----
const KINDS: { value: MarkKind; label: string }[] = [
  { value: "event", label: "events" },
  { value: "chapter", label: "chapters" },
  { value: "birth", label: "births and deaths" },
  { value: "move", label: "movements" },
];
const remembered = () => {
  try {
    return JSON.parse(localStorage.getItem(`timeline:${worldSlug.value}`) ?? "{}") as Record<string, string>;
  } catch {
    return {};
  }
};
onMounted(() => {
  // a page opened without filters in the address starts from the last used
  const r = remembered();
  const missing = Object.fromEntries(["kinds", "entries", "era", "standings"].filter((k) => !route.query[k] && r[k]).map((k) => [k, r[k]]));
  if (Object.keys(missing).length) setQuery(missing);
});
watch(() => [route.query.kinds, route.query.entries, route.query.era, route.query.standings], () => {
  try {
    localStorage.setItem(`timeline:${worldSlug.value}`, JSON.stringify({ kinds: route.query.kinds ?? "", entries: route.query.entries ?? "", era: route.query.era ?? "", standings: route.query.standings ?? "" }));
  } catch {
    /* storage unavailable */
  }
});
const kinds = computed(() => {
  const k = list("kinds") as MarkKind[];
  const set = new Set<MarkKind>(k.length ? k : ["event", "chapter", "birth", "move"]);
  if (set.has("birth")) set.add("death");
  return set;
});
const entries = computed(() => new Set(list("entries")));
const standings = computed(() => new Set(list("standings").length ? list("standings") : ["canon", "planned", "rumour"]));
const eraFilter = computed(() => (typeof route.query.era === "string" ? route.query.era : ""));
function toggleKind(k: MarkKind) {
  const next = new Set(kinds.value);
  next.delete("death");
  if (next.has(k)) next.delete(k);
  else next.add(k);
  setQuery({ kinds: [...next].join(",") || "none" });
}
function toggleStanding(s: string) {
  const next = new Set(standings.value);
  if (next.has(s)) next.delete(s);
  else next.add(s);
  setQuery({ standings: [...next].join(",") });
}

// ---- the model and the lanes ----
const eras = computed(() => cards.eras);
const model = computed(() => buildModel(cards.cards, cards.timeline, eras.value, chron.value));
const laneKeys = computed(() => list("lanes"));
const folded = computed(() => new Set(list("fold")));
const lanes = computed<Lane[]>(() => buildLanes(model.value, laneKeys.value, { kinds: kinds.value, entries: entries.value, standings: standings.value }, cards.byId, cards.timeline, graph.value, chron.value));
const eraSpan = computed(() => eras.value.find((e) => e.id === eraFilter.value) ?? null);
/** the times on the axis: History is cut off where the book begins; an era filter keeps only its span */
const cutoff = computed(() => (view.value === "history" ? (model.value.book?.start ?? null) : null));
const visibleTimes = computed(() => {
  let ts = model.value.times;
  if (cutoff.value !== null) ts = ts.filter((t) => t < cutoff.value!);
  const e = eraSpan.value;
  if (e) ts = ts.filter((t) => t >= e.start && (e.end === null || t <= e.end));
  return ts;
});
const keep = (m: Mark) => (cutoff.value === null || m.t < cutoff.value) && (!eraSpan.value || (m.t >= eraSpan.value.start && (eraSpan.value.end === null || m.t <= eraSpan.value.end)));

// ---- geometry ----
const wrap = ref<HTMLElement | null>(null);
const W = ref(900);
const OVERVIEW_H = 34;
/** the axis: a strip of era names (a row for the outer eras, one for those nested in them), then the ticks */
const ERA_ROW = 14;
const ERA_H = 2 * ERA_ROW + 2;
const AXIS_H = ERA_H + 26;
const FOLDED_H = 20;
const TOP = OVERVIEW_H + AXIS_H + 8;
/** names stand in rows above a lane's line; the events lane has three, the others two */
const ROW_H = 14;
const FONT = '11.5px system-ui, -apple-system, "Segoe UI", sans-serif';
const TITLE_FONT = `600 ${FONT}`;
const rowsOf = (l: Lane) => (l.kind === "events" ? 3 : 2);
/** a lane's own bars (places, roles, nested eras) sit under its title, above the names */
const headOf = (l: Lane) => (l.kind === "events" || l.kind === "book" ? 14 : 26);
const heightOf = (l: Lane) => headOf(l) + rowsOf(l) * ROW_H + 16;
const laneY = computed(() => {
  const ys: number[] = [];
  const hs: number[] = [];
  let y = TOP;
  for (const l of lanes.value) {
    ys.push(y);
    const h = folded.value.has(l.key) ? FOLDED_H : heightOf(l);
    hs.push(h);
    y += h;
  }
  return { ys, hs, height: y + 10 };
});
let ro: ResizeObserver | null = null;
onMounted(() => {
  const el = wrap.value;
  if (!el) return;
  W.value = el.clientWidth || 900;
  ro = new ResizeObserver(() => (W.value = el.clientWidth || W.value));
  ro.observe(el);
});
onBeforeUnmount(() => ro?.disconnect());

// ---- zoom and pan: a scale (px per unit) and an offset (px); the axis is worked out again as the scale changes ----
const k = ref(1);
const offset = ref(0);
const foldAt = computed(() => foldAtFor(W.value));
const axisAt = (kk: number, pad = 0) => makeAxis(visibleTimes.value, kk, pad, foldAt.value);
const fitK = computed(() => fitScale(visibleTimes.value, W.value - 40, 40, foldAt.value));
function fit() {
  k.value = fitK.value;
  // what doesn't fill the width sits in the middle of it
  const w = axisAt(fitK.value).width;
  offset.value = -Math.max(20, (W.value - w) / 2);
}
watch([visibleTimes, W], fit, { immediate: true });
const axis = computed(() => axisAt(k.value));
const step = computed(() => stepOf(k.value));
/** the axis the clusters are worked out at: once per zoom step */
const stepAxis = computed(() => axisAt(scaleOfStep(step.value)));
// marks closer than a cluster's width merge (a cluster's circle is at most 22 px across)
const clustered = computed(() => lanes.value.map((l) => cluster(l.marks.filter(keep), stepAxis.value, 24)));
const far = computed(() => k.value <= fitK.value * 1.01 && model.value.marks.length > 200);
const X = (t: number) => axis.value.x(t) - offset.value;
function zoomAt(px: number, factor: number) {
  const t = axis.value.t(px + offset.value);
  const next = Math.min(Math.max(k.value * factor, fitK.value / 8), 2000);
  k.value = next;
  offset.value = axisAt(next).x(t) - px;
}
function zoomTo(t1: number, t2: number) {
  if (!(t2 > t1)) return;
  let lo = 1e-9;
  let hi = 1e6;
  for (let i = 0; i < 50; i++) {
    const mid = Math.sqrt(lo * hi);
    const a = axisAt(mid);
    if (a.x(t2) - a.x(t1) <= W.value * 0.8) lo = mid;
    else hi = mid;
  }
  k.value = lo;
  offset.value = axisAt(lo).x(t1) - W.value * 0.1;
}

// what is on screen: only the items in view are drawn (a few hundred at most)
const inView = (x: number) => x > -60 && x < W.value + 60;
const shown = computed(() =>
  clustered.value.map((items) => {
    const out: { item: Item; x: number; label: string }[] = [];
    for (let i = 0; i < items.length; i++) {
      const it = items[i]!;
      const x = X(it.mark ? it.mark.t : it.cluster!.t);
      if (!inView(x)) continue;
      out.push({ item: it, x, label: "" });
    }
    return out;
  }),
);
/** each name on screen: in which row, on which side, and how much of it (world/timeline.ts placeLabels) */
const labelSpots = computed(() =>
  shown.value.map((items, li) => {
    const l = lanes.value[li];
    if (far.value || !l || folded.value.has(l.key)) return items.map(() => null);
    return placeLabels(
      items.map((o) => ({ x: o.x, text: o.item.mark ? o.item.mark.label : o.item.cluster!.breakdown, pad: o.item.cluster ? 14 : 7 })),
      { rows: rowsOf(l), width: W.value, measure: (t) => textWidth(t, FONT), fit: (t, room) => fitText(t, room, FONT) },
    );
  }),
);
// ticks, leaving out any whose label would sit on a fold's or be cut off at an edge
const tickList = computed(() =>
  ticks(axis.value, offset.value, offset.value + W.value)
    .map((t) => ({ t, x: X(t), era: eraAt(t, eras.value), half: textWidth(numberText(t), FONT) / 2 + 3 }))
    .filter((tk) => tk.x - tk.half >= 0 && tk.x + tk.half <= W.value)
    .filter((tk) => !axis.value.folds.some((f) => tk.x + tk.half > f.x - offset.value && tk.x - tk.half < f.x - offset.value + f.w)),
);
const SEG_FONT = '10.5px system-ui, -apple-system, "Segoe UI", sans-serif';
/** the lane's title (or its counts, folded) and, unfolded, how many of its own things are outside time */
const titleText = (l: Lane) => (folded.value.has(l.key) ? l.counts : l.title);
const titleWidth = (l: Lane) => Math.min(260, textWidth(titleText(l), TITLE_FONT) + 10);
const outsideNote = (l: Lane) => (l.outside.length && !folded.value.has(l.key) ? `${l.outside.length} outside time` : "");
/** each segment's name, after the lane's title, where it fits before the segment ends and clear of the name before
 * it (shortened, or left out) */
const segLabels = computed(() =>
  lanes.value.map((l) => {
    let end = titleWidth(l) + 6;
    return l.segments.map((s) => {
      if (s.tone !== "place" && s.tone !== "role") return null;
      const x = Math.max(end, X(s.t) + 2);
      const room = Math.min(W.value, X(s.t2)) - x - 4;
      if (room < 36) return null;
      const text = fitText(s.label, room, SEG_FONT);
      if (!text) return null;
      end = x + textWidth(text, SEG_FONT) + 8;
      return { x, text };
    });
  }),
);
const foldsShown = computed(() => axis.value.folds.map((f) => ({ ...f, sx: f.x - offset.value })).filter((f) => f.sx + f.w > 0 && f.sx < W.value));
const foldText = (n: number) => `· ${numberText(Math.round(n))} ${Math.round(n) === 1 ? unit.value.unit : unit.value.units} ·`;
const ERA_FONT = `600 ${FONT}`;
const eraBands = computed(() => {
  const bands = eras.value
    .filter((e) => (!eraSpan.value || e === eraSpan.value || (e.start >= eraSpan.value.start && (eraSpan.value.end === null || (e.end ?? Infinity) <= eraSpan.value.end))))
    .map((e) => {
      const x1 = Math.max(-10, X(e.start));
      const x2 = Math.min(W.value + 10, e.end === null ? W.value + 10 : X(e.end));
      // outer eras name themselves in the strip's first row, eras nested in them in the second
      const row = Math.min(e.depth, 1);
      return { era: e, x1, x2, row, inset: Math.min(e.depth, 3) * 5, name: "", nx: Math.max(x1, 0) + 4 };
    })
    .filter((b) => b.x2 > b.x1);
  // each name where it fits in its band and before the next name in its row (shortened, or left out)
  for (const row of [0, 1]) {
    const inRow = bands.filter((b) => b.row === row).sort((a, b) => a.nx - b.nx);
    inRow.forEach((b, i) => {
      const next = inRow[i + 1]?.nx ?? Infinity;
      const room = Math.min(b.x2, next, W.value) - b.nx - 8;
      b.name = room > 30 ? fitText(b.era.name, room, ERA_FONT) : "";
    });
  }
  return bands;
});
const bookBand = computed(() => (model.value.book && cutoff.value === null ? { x1: X(model.value.book.start), x2: Math.max(X(model.value.book.end), X(model.value.book.start) + 4) } : null));

// ---- the overview strip: the whole timeline small, with the part on screen as a frame ----
const overviewAxis = computed(() => {
  const kk = fitScale(visibleTimes.value, W.value, 10, foldAt.value);
  return axisAt(kk, 10 + Math.max(0, (W.value - axisAt(kk, 10).width) / 2));
});
const density = computed(() => {
  const bins = new Array(Math.max(1, Math.floor(W.value / 6))).fill(0) as number[];
  for (const m of model.value.marks) {
    if (!keep(m)) continue;
    const i = Math.floor(overviewAxis.value.x(m.t) / 6);
    if (i >= 0 && i < bins.length) bins[i]!++;
  }
  const top = Math.max(1, ...bins);
  return bins.map((n, i) => ({ x: i * 6, h: (n / top) * (OVERVIEW_H - 10) })).filter((b) => b.h > 0);
});
const frame = computed(() => {
  const t1 = axis.value.t(offset.value);
  const t2 = axis.value.t(offset.value + W.value);
  const x1 = Math.max(0, overviewAxis.value.x(t1));
  const x2 = Math.min(W.value, overviewAxis.value.x(t2));
  return { x1, x2: Math.max(x2, x1 + 6) };
});

// ---- brushing a span (dragging along the axis), kept in the address, cleared with Esc or its × ----
const brushFrom = computed(() => (typeof route.query.from === "string" ? Number(route.query.from) : null));
const brushTo = computed(() => (typeof route.query.to === "string" ? Number(route.query.to) : null));
const brush = computed(() => (brushFrom.value !== null && brushTo.value !== null && Number.isFinite(brushFrom.value) && Number.isFinite(brushTo.value) ? { from: Math.min(brushFrom.value, brushTo.value), to: Math.max(brushFrom.value, brushTo.value) } : null));
const brushing = ref<{ x0: number; x1: number } | null>(null);
function setBrush(t1: number, t2: number) {
  const r = (t: number) => String(Math.round(t * 100) / 100);
  setQuery({ from: r(Math.min(t1, t2)), to: r(Math.max(t1, t2)) });
}
const clearBrush = () => setQuery({ from: undefined, to: undefined });
// the chart beside the lanes follows the brushed span (docs/SPEC.md §13.7.5); the span is kept on the device too, for
// the chart page's "Follow the Timeline"
const chartOpen = computed(() => route.query.chart === "1");
watch(brush, (b) => {
  // leaving the page changes the address before the page goes: that isn't clearing the span
  if (route.name !== "timeline") return;
  try {
    if (b) localStorage.setItem(`timeline-span:${worldSlug.value}`, JSON.stringify(b));
    else localStorage.removeItem(`timeline-span:${worldSlug.value}`);
  } catch {
    /* storage unavailable */
  }
}, { immediate: true });
const spanLine = computed(() => {
  const b = brush.value;
  if (!b) return "";
  const n = Math.round(b.to - b.from);
  const era = eraAt((b.from + b.to) / 2, eras.value);
  return `${unit.value.unit} ${numberText(b.from)}–${numberText(b.to)} · ${n} ${n === 1 ? unit.value.unit : unit.value.units}${era ? ` · ${era.name}` : ""}`;
});
const spanMarks = computed(() => (brush.value ? inSpan(model.value.marks.filter(keep), brush.value.from, brush.value.to) : []));
const spanGroups = computed(() =>
  KINDS.map((g) => ({ ...g, marks: spanMarks.value.filter((m) => (g.value === "birth" ? m.kind === "birth" || m.kind === "death" : m.kind === g.value)) })).filter((g) => g.marks.length),
);
const dimOutside = (x: number) => !!brush.value && (x < X(brush.value.from) - 1 || x > X(brush.value.to) + 1);

// ---- pointers: drag to pan, along the axis (or the overview) to brush, two fingers to pinch ----
const svg = ref<SVGSVGElement | null>(null);
const pointers = new Map<number, { x: number; y: number }>();
let drag: null | { mode: "pan" | "brush" | "frame" | "frame-l" | "frame-r"; x: number; offset: number; k: number } = null;
let pinch: null | { d: number; k: number; mid: number } = null;
const local = (e: PointerEvent | WheelEvent | MouseEvent) => {
  const r = svg.value!.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
};
// a drag can start anywhere, on a mark too; the pointer is captured only once it moves, so a click on a mark still
// reaches the mark, and a drag that started on one doesn't open it
let downAt: { x: number; y: number; id: number } | null = null;
let moved = false;
function down(e: PointerEvent) {
  const p = local(e);
  pointers.set(e.pointerId, p);
  downAt = { ...p, id: e.pointerId };
  moved = false;
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    pinch = { d: Math.abs(a!.x - b!.x) || 1, k: k.value, mid: (a!.x + b!.x) / 2 };
    drag = null;
    return;
  }
  if (p.y < OVERVIEW_H) {
    const f = frame.value;
    const mode = Math.abs(p.x - f.x1) < 7 ? "frame-l" : Math.abs(p.x - f.x2) < 7 ? "frame-r" : p.x > f.x1 && p.x < f.x2 ? "frame" : null;
    if (mode) drag = { mode, x: p.x, offset: offset.value, k: k.value };
    else {
      // a click on the overview outside the frame centres the axis there
      const t = overviewAxis.value.t(p.x);
      offset.value = axis.value.x(t) - W.value / 2;
    }
    return;
  }
  drag = { mode: p.y < OVERVIEW_H + AXIS_H ? "brush" : "pan", x: p.x, offset: offset.value, k: k.value };
  if (drag.mode === "brush") brushing.value = { x0: p.x, x1: p.x };
}
let frameRequested = false;
let pending: (() => void) | null = null;
const onFrame = (fn: () => void) => {
  pending = fn;
  if (frameRequested) return;
  frameRequested = true;
  requestAnimationFrame(() => {
    frameRequested = false;
    pending?.();
    pending = null;
  });
};
function move(e: PointerEvent) {
  if (!pointers.has(e.pointerId)) return;
  const p = local(e);
  pointers.set(e.pointerId, p);
  if (!moved && downAt && Math.hypot(p.x - downAt.x, p.y - downAt.y) > 4) {
    moved = true;
    touchEnd();
    svg.value?.setPointerCapture(e.pointerId);
  }
  if (pinch && pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    const d = Math.abs(a!.x - b!.x) || 1;
    const target = pinch.k * (d / pinch.d);
    const mid = pinch.mid;
    onFrame(() => zoomAt(mid, target / k.value));
    return;
  }
  if (!drag) return;
  const d = drag;
  if (d.mode === "pan") onFrame(() => (offset.value = d.offset - (p.x - d.x)));
  else if (d.mode === "brush") brushing.value = { x0: brushing.value!.x0, x1: p.x };
  else if (d.mode === "frame") {
    // dragging the overview's frame pans the Timeline
    const t = overviewAxis.value.t(overviewAxis.value.x(axis.value.t(d.offset)) + (p.x - d.x));
    onFrame(() => (offset.value = axis.value.x(t)));
  } else {
    // resizing it zooms
    const f = frame.value;
    const [x1, x2] = d.mode === "frame-l" ? [p.x, f.x2] : [f.x1, p.x];
    if (x2 - x1 > 8) onFrame(() => zoomTo(overviewAxis.value.t(x1), overviewAxis.value.t(x2)));
  }
}
function up(e: PointerEvent) {
  pointers.delete(e.pointerId);
  if (pointers.size < 2) pinch = null;
  if (drag?.mode === "brush" && brushing.value) {
    const { x0, x1 } = brushing.value;
    if (Math.abs(x1 - x0) > 4) setBrush(axis.value.t(Math.min(x0, x1) + offset.value), axis.value.t(Math.max(x0, x1) + offset.value));
    brushing.value = null;
  }
  drag = null;
}
function wheel(e: WheelEvent) {
  const p = local(e);
  const factor = Math.pow(1.0015, -e.deltaY);
  onFrame(() => zoomAt(p.x, factor));
}
function key(e: KeyboardEvent) {
  if (e.key === "Escape") {
    // kept arrows go first, before a brushed span is cleared (docs/SPEC.md §14.7)
    if (kept.value) letGo();
    else if (focus.value) focus.value = null;
    else clearBrush();
    return;
  }
  if (focus.value && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Enter"].includes(e.key)) {
    e.preventDefault();
    moveFocus(e.key);
    return;
  }
  if (e.key === "+" || e.key === "=") zoomAt(W.value / 2, 1.4);
  else if (e.key === "-") zoomAt(W.value / 2, 1 / 1.4);
  else if (e.key === "ArrowLeft") offset.value -= W.value * 0.15;
  else if (e.key === "ArrowRight") offset.value += W.value * 0.15;
  else if (e.key === "Home" || e.key === "f") fit();
  else if (e.key === "Enter" || e.key === " ") {
    // start moving from mark to mark
    const lane = shown.value.findIndex((s) => s.length);
    if (lane >= 0) focus.value = { lane, i: 0 };
  } else return;
  e.preventDefault();
}

// ---- marks: from one to the next by keyboard, a card on resting, opening on click ----
const focus = ref<{ lane: number; i: number } | null>(null);
function moveFocus(k2: string) {
  const f = focus.value!;
  const items = shown.value[f.lane] ?? [];
  if (k2 === "Enter") {
    const it = items[f.i]?.item;
    if (it) openItem(it);
    return;
  }
  if (k2 === "ArrowRight") focus.value = { lane: f.lane, i: Math.min(items.length - 1, f.i + 1) };
  else if (k2 === "ArrowLeft") focus.value = { lane: f.lane, i: Math.max(0, f.i - 1) };
  else {
    const dir = k2 === "ArrowDown" ? 1 : -1;
    for (let l = f.lane + dir; l >= 0 && l < shown.value.length; l += dir) {
      if (shown.value[l]!.length) {
        const x = items[f.i]?.x ?? 0;
        const next = shown.value[l]!;
        let best = 0;
        next.forEach((o, i) => Math.abs(o.x - x) < Math.abs(next[best]!.x - x) && (best = i));
        focus.value = { lane: l, i: best };
        break;
      }
    }
  }
  const it = shown.value[focus.value!.lane]?.[focus.value!.i];
  if (it && (it.x < 20 || it.x > W.value - 20)) offset.value += it.x - W.value / 2;
}
const chapters = computed(() => new Map(cards.timeline.map((c) => [c.id, c])));
function openItem(it: Item) {
  if (it.cluster) {
    const ts = it.cluster.marks.map((m) => m.t);
    zoomTo(Math.min(...ts) - 0.5, Math.max(...ts) + 0.5);
    return;
  }
  const m = it.mark!;
  if (m.kind === "chapter" || (m.kind === "move" && m.chapter)) void router.push({ name: "chapter", params: { world: worldSlug.value, id: m.chapter! } });
  else if (m.entity) void router.push({ name: "entity", params: { world: worldSlug.value, id: m.entity } });
}
function cardFor(it: Item): HTMLElement | null {
  if (it.mark?.entity && (it.mark.kind === "event" || it.mark.kind === "birth" || it.mark.kind === "death")) return null;
  const root = document.createElement("div");
  root.className = "qcard";
  root.dataset.testid = "name-card";
  const add = (cls: string, text: string) => {
    const d = document.createElement("div");
    d.className = cls;
    d.textContent = text;
    root.append(d);
  };
  if (it.cluster) {
    add("qcard-head", it.cluster.breakdown);
    for (const m of it.cluster.marks.slice(0, 8)) add("qcard-summary", m.label);
    if (it.cluster.marks.length > 8) add("qcard-also", `and ${it.cluster.marks.length - 8} more · double-click to zoom in`);
    return root;
  }
  const ch: StoryChapter | undefined = it.mark?.chapter ? chapters.value.get(it.mark.chapter) : undefined;
  if (ch) {
    add("qcard-head", ch.title);
    if (ch.summary) add("qcard-summary", ch.summary);
    add("qcard-also", [ch.told_as, timeText(ch.time_at != null ? ch : { time_at: ch.set_time ?? null, time_approx: ch.set_approx }, unit.value), ch.status].filter(Boolean).join(" · "));
    if (it.mark!.kind === "move") add("qcard-summary", it.mark!.label);
    return root;
  }
  add("qcard-summary", it.mark!.label);
  return root;
}
function enter(e: PointerEvent, it: Item) {
  const el = e.currentTarget as HTMLElement;
  const custom = cardFor(it);
  if (!custom && it.mark?.entity) {
    // the same card as the editor's, as of that time; an event's shows its cause arrows while it shows
    const t = it.mark.t;
    const ev = it.mark.kind === "event" ? it.mark.entity : null;
    if (ev) hoverEv.value = ev;
    showCard(el, cards.asOf(cards.byId.get(it.mark.entity), { time: t }), () => openItem(it), 350, (kind, label) => cards.several(kind, label), ev ? () => arrowChips(ev) : undefined);
  } else if (custom) showCustom(el, custom);
}
let customShown: HTMLElement | null = null;
let customTimer = 0;
function showCustom(anchor: HTMLElement, dom: HTMLElement) {
  window.clearTimeout(customTimer);
  customTimer = window.setTimeout(() => {
    hideCustom();
    dom.classList.add("qcard-floating");
    document.body.append(dom);
    const r = anchor.getBoundingClientRect();
    dom.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - dom.offsetWidth - 8))}px`;
    dom.style.top = `${r.bottom + 6}px`;
    customShown = dom;
  }, 350);
}
function hideCustom() {
  window.clearTimeout(customTimer);
  customShown?.remove();
  customShown = null;
}
function leave() {
  hideCard();
  hideCustom();
  hoverEv.value = null;
}

// ---- cause arrows (docs/SPEC.md §14.7): an event's causes and effects while its card shows, or kept ----
const links = computed(() => (graph.value ? causeLinks(graph.value) : []));
const hoverEv = ref<string | null>(null);
const kept = computed(() => (typeof route.query.keep === "string" ? route.query.keep : null));
const whole = computed(() => route.query.chain === "1");
const activeEv = computed(() => kept.value ?? hoverEv.value);
const keepArrows = (id: string, chain = false) => setQuery({ keep: id, chain: chain ? "1" : undefined });
const letGo = () => setQuery({ keep: undefined, chain: undefined });
/** On an event's card: keep its arrows, or follow the whole chain (which keeps them too). */
function arrowChips(id: string): HTMLElement | null {
  if (!links.value.some((l) => l.cause === id || l.effect === id)) return null;
  const row = document.createElement("div");
  row.className = "qrow";
  for (const [label, chain] of [["Keep arrows", false], ["Whole chain", true]] as const) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "qchip";
    b.textContent = label;
    b.addEventListener("click", () => {
      hideCard(true);
      keepArrows(id, chain);
    });
    row.append(b);
  }
  return row;
}
const eventsLane = computed(() => Math.max(0, lanes.value.findIndex((l) => l.kind === "events")));
/** Where an event is drawn now: its mark, the cluster it is in, the outside-time strip, or (off screen) the edge. */
function placeOf(id: string): { x: number; y: number; edge?: string; t?: number } | null {
  for (let li = 0; li < shown.value.length; li++) {
    for (const o of shown.value[li]!) {
      const it = o.item;
      if ((it.mark?.kind === "event" && it.mark.entity === id) || it.cluster?.marks.some((m) => m.kind === "event" && m.entity === id)) {
        return { x: o.x, y: laneY.value.ys[li]! + laneY.value.hs[li]! - 10 };
      }
    }
  }
  const ev = lanes.value[eventsLane.value];
  const y = (laneY.value.ys[eventsLane.value] ?? 0) + (laneY.value.hs[eventsLane.value] ?? 0) - 10;
  // outside time: the lane's "n outside time" beside its title
  if (model.value.outside.some((o) => o.entity === id)) return { x: ev ? titleWidth(ev) + 40 : 60, y: (laneY.value.ys[eventsLane.value] ?? 0) + 12 };
  const m = model.value.marks.find((x) => x.id === `ev:${id}`);
  if (!m) return null;
  const x = X(m.t);
  return { x: Math.max(4, Math.min(W.value - 4, x)), y, edge: x < 0 || x > W.value ? (cards.byId.get(id)?.name ?? "") : undefined, t: m.t };
}
const timeOf = (id: string) => model.value.marks.find((x) => x.id === `ev:${id}`)?.t;
const arrows = computed(() => {
  const id = activeEv.value;
  if (!id || view.value === "told") return [];
  return linksOf(links.value, id, whole.value || !!(kept.value && whole.value))
    .filter(({ link }) => standings.value.has(link.standing))
    .flatMap(({ link, depth }) => {
      const a = placeOf(link.cause);
      const b = placeOf(link.effect);
      if (!a || !b) return [];
      const ta = timeOf(link.cause);
      const tb = timeOf(link.effect);
      return [{
        key: link.id, d: arrowPath(a.x, a.y, b.x, b.y), dashed: link.standing !== "canon", opacity: Math.max(0.3, 1 - 0.22 * (depth - 1)),
        before: ta !== undefined && tb !== undefined && tb < ta, mid: { x: (a.x + b.x) / 2, y: Math.min(a.y, b.y) - Math.min(70, 18 + Math.abs(b.x - a.x) / 6) / 2 },
        edges: [a, b].filter((p) => p.edge).map((p) => ({ x: p.x, y: p.y, name: p.edge!, t: p.t! })),
        from: cards.byId.get(link.cause)?.name ?? "", to: cards.byId.get(link.effect)?.name ?? "",
      }];
    });
});
/** The kept event's card: its name and the linked events not placed yet ("led to: the Second Flood (not placed yet)"). */
const keptCard = computed(() => {
  const id = kept.value;
  if (!id) return null;
  const notPlaced = linksOf(links.value, id, false)
    .map(({ link }) => ({ other: link.cause === id ? link.effect : link.cause, reads: link.cause === id ? link.reads : "followed from" }))
    .filter((x) => !model.value.marks.some((m) => m.id === `ev:${x.other}`) && !model.value.outside.some((o) => o.entity === x.other))
    .map((x) => ({ ...x, name: cards.byId.get(x.other)?.name ?? "" }));
  return { name: cards.byId.get(id)?.name ?? "", notPlaced };
});
const panTo = (t: number) => (offset.value += X(t) - W.value / 2);
onBeforeUnmount(leave);
// a long-press on the phone shows the card, as resting does
let press = 0;
const touchStart = (e: PointerEvent, it: Item) => {
  if (e.pointerType !== "touch") return;
  window.clearTimeout(press);
  press = window.setTimeout(() => enter(e, it), 450);
};
const touchEnd = () => window.clearTimeout(press);

// ---- lanes: add (characters, factions, eras), fold to a line, remove ----
const picking = ref(false);
const laneChoices = computed(() => [
  ...cards.names.filter((n) => n.kind === "character" || n.kind === "faction" || n.kind === "place" || n.kind === "species").filter((n) => !laneKeys.value.includes(n.id)),
  ...eras.value.filter((e) => !laneKeys.value.includes(e.id)).map((e) => ({ id: e.id, name: e.name, kind: "event" as const })),
]);
const addLane = (id: string) => {
  picking.value = false;
  setQuery({ lanes: [...laneKeys.value, id].join(",") });
};
const removeLane = (id: string) => setQuery({ lanes: laneKeys.value.filter((x) => x !== id).join(",") || undefined, fold: [...folded.value].filter((x) => x !== id).join(",") || undefined });
const toggleFold = (id: string) => {
  const next = new Set(folded.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  setQuery({ fold: [...next].join(",") || undefined });
};
const entryNames = computed(() => [...entries.value].map((id) => cards.byId.get(id)).filter(Boolean));

// ---- the tray: events not placed yet, each with When… to set it in place ----
const whenDraft = ref<Record<string, string>>({});
async function placeEvent(id: string) {
  const t = parseTime(whenDraft.value[id] ?? "");
  if (t === null) return;
  try {
    const { entity } = await getEntity(worldSlug.value, id);
    await updateEntity(worldSlug.value, entity, { time_at: t, time_chapter_id: null, outside_time: false });
    whenDraft.value[id] = "";
    await cards.refresh(worldSlug.value);
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// ---- the told view: chapters in book order, with where each sits in happened order ----
const told = computed(() => {
  const tl = cards.timeline;
  const onClock = tl.filter((c) => c.clock !== null).length || 1;
  const byChapter = new Map<string, { told: string[]; happens: string[]; life: string[] }>();
  const get2 = (id: string) => byChapter.get(id) ?? byChapter.set(id, { told: [], happens: [], life: [] }).get(id)!;
  const toldIds = new Set<string>();
  for (const t of chron.value?.tellings ?? []) {
    if (!t.chapter_id) continue;
    toldIds.add(t.event_id);
    const name = cards.byId.get(t.event_id)?.name;
    if (name && !get2(t.chapter_id).told.includes(name)) get2(t.chapter_id).told.push(name);
  }
  const inChapter = new Set<string>();
  for (const c of cards.cards) {
    if (c.kind === "event" && c.when?.chapter) {
      inChapter.add(c.id);
      get2(c.when.chapter).happens.push(c.name);
    }
    if (c.kind === "character") {
      for (const f of c.facts) {
        const label = f.label.trim().toLowerCase();
        if (!f.from) continue;
        if (label === "born") get2(f.from).life.push(`${c.name} born`);
        else if (label === "status" && /\b(dead|deceased|died|killed|slain|murdered)\b/i.test(f.value)) get2(f.from).life.push(`${c.name} dies`);
      }
    }
  }
  const rows = tl.map((c) => ({ c, at: c.clock === null ? null : (c.clock ?? c.index) / onClock, ...(byChapter.get(c.id) ?? { told: [], happens: [], life: [] }), era: eraAt(c.outside_time ? null : (c.time_at ?? c.set_time), eras.value) }));
  const notInBook = cards.cards.filter((c) => c.kind === "event" && !toldIds.has(c.id) && !inChapter.has(c.id) && !eras.value.some((e) => e.id === c.id)).map((c) => ({ id: c.id, name: c.name }));
  return { rows, notInBook };
});
const whenOf = (c: StoryChapter) => (c.outside_time ? "outside time" : c.early ? "before the story" : timeText(c.time_at != null ? c : { time_at: c.set_time ?? null, time_approx: c.set_approx }, unit.value));

const historyEmpty = computed(() => view.value === "history" && !model.value.book);
const focusRing = (l: number, i: number) => focus.value?.lane === l && focus.value.i === i;
const laneOutside = (l: Lane) => l.outside.map((o) => o.label).join(" · ");
const tipFor = (it: Item) => (it.cluster ? it.cluster.breakdown : it.mark!.label);
const eraTitle = (e: Era) => `${e.name}: ${timeText({ time_at: e.start, time_end: e.end, time_approx: e.approx }, unit.value)}${e.end === null ? " onward" : ""}`;
void nextTick;
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Timeline</h1>
      </div>
      <div class="actions tabs">
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': view === 'happened' }" data-testid="tab-happened" @click="setQuery({ view: undefined })">Happened</button>
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': view === 'told' }" data-testid="tab-told" @click="setQuery({ view: 'told' })">Told</button>
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': view === 'history' }" data-testid="tab-history" @click="setQuery({ view: 'history' })">History</button>
      </div>
    </div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <template v-if="view !== 'told'">
      <div class="toolbar timeline-tools">
        <button type="button" class="btn btn-sm" data-testid="fit" @click="fit">Fit</button>
        <button type="button" class="btn btn-sm" aria-label="Zoom in" @click="zoomAt(W / 2, 1.5)">+</button>
        <button type="button" class="btn btn-sm" aria-label="Zoom out" @click="zoomAt(W / 2, 1 / 1.5)">−</button>
        <span v-for="kk in KINDS" :key="kk.value" class="chip static"><label><input type="checkbox" :checked="kinds.has(kk.value)" :data-testid="`kind-${kk.value}`" @change="toggleKind(kk.value)" /> {{ kk.label }}</label></span>
        <span v-for="s in ['planned', 'rumour']" :key="s" class="chip static"><label><input type="checkbox" :checked="standings.has(s)" @change="toggleStanding(s)" /> {{ s }}</label></span>
        <label v-if="eras.length" class="small muted">Era
          <select class="filter" :value="eraFilter" data-testid="era-filter" @change="setQuery({ era: ($event.target as HTMLSelectElement).value || undefined })">
            <option value="">every era</option>
            <option v-for="e in eras" :key="e.id" :value="e.id">{{ e.name }}</option>
          </select>
        </label>
        <span class="entries-filter">
          <span v-for="e in entryNames" :key="e!.id" class="chip static" :class="`k-${e!.kind}`">{{ e!.name }}<button type="button" class="chip-x" :aria-label="`Not only ${e!.name}`" @click="setQuery({ entries: [...entries].filter((x) => x !== e!.id).join(',') || undefined })">×</button></span>
          <EntityPicker :entities="cards.names" :exclude="[...entries]" placeholder="Only about…" @pick="(e) => setQuery({ entries: [...entries, e.id].join(',') })" @cancel="() => {}" />
        </span>
        <button type="button" class="btn btn-sm" data-testid="add-lane" @click="picking = !picking">Lanes…</button>
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': chartOpen }" data-testid="open-chart" @click="setQuery({ chart: chartOpen ? undefined : '1' })">Chart</button>
      </div>
      <div v-if="picking" class="card lane-pick" data-testid="lane-pick">
        <EntityPicker :entities="laneChoices" placeholder="A lane for… (a character, a faction, an era)" @pick="(e) => addLane(e.id)" @cancel="picking = false" />
      </div>
      <p v-if="historyEmpty" class="notice small" data-testid="history-empty">Set a time on a chapter to place the book among them.</p>

      <div class="timeline-main" :class="{ 'with-chart': chartOpen }">
      <div ref="wrap" class="timeline-wrap">
        <svg
          v-if="visibleTimes.length"
          ref="svg"
          class="timeline"
          :width="W"
          :height="laneY.height"
          tabindex="0"
          role="application"
          aria-label="Timeline: drag to move, scroll or pinch to zoom, drag along the axis to mark a span, + and − to zoom, Enter to move from mark to mark"
          data-testid="timeline"
          :data-far="far ? 'yes' : 'no'"
          :data-step="step"
          @wheel.prevent="wheel"
          @pointerdown="down"
          @pointermove="move"
          @pointerup="up"
          @pointercancel="up"
          @keydown="key"
        >
          <!-- eras: background bands across every lane, nested ones thinner inside -->
          <g class="tl-eras">
            <rect v-for="b in eraBands" :key="b.era.id" :class="`era-${b.era.colour} tl-era`" :x="b.x1" :y="OVERVIEW_H + 1 + b.row * ERA_ROW + b.inset" :width="b.x2 - b.x1" :height="laneY.height - OVERVIEW_H - 1 - b.row * ERA_ROW - b.inset * 2" :data-era="b.era.name" data-testid="era-band"
              @dblclick="zoomTo(b.era.start, b.era.end ?? b.era.start + 1)">
              <title>{{ eraTitle(b.era) }}</title>
            </rect>
            <text v-for="b in eraBands.filter((x) => x.name)" :key="`n-${b.era.id}`" :class="`era-${b.era.colour} tl-era-name`" :x="b.nx" :y="OVERVIEW_H + 11 + b.row * ERA_ROW" data-testid="era-name">{{ b.name }}<title>{{ eraTitle(b.era) }}</title></text>
          </g>

          <!-- the overview: the whole timeline small, eras, how dense the marks are, the book, the part on screen -->
          <g class="tl-overview" data-testid="overview">
            <rect class="tl-overview-bg" x="0" y="0" :width="W" :height="OVERVIEW_H - 4" />
            <rect v-for="e in eras" :key="`o-${e.id}`" :class="`era-${e.colour} tl-era`" :x="overviewAxis.x(e.start)" y="2" :width="Math.max(2, (e.end === null ? W : overviewAxis.x(e.end)) - overviewAxis.x(e.start))" :height="OVERVIEW_H - 8" />
            <rect v-for="(b, i) in density" :key="`d-${i}`" class="tl-density" :x="b.x" :y="OVERVIEW_H - 6 - b.h" width="5" :height="b.h" />
            <rect v-if="model.book" class="tl-book-band" :x="overviewAxis.x(model.book.start)" :y="OVERVIEW_H - 8" :width="Math.max(3, overviewAxis.x(model.book.end) - overviewAxis.x(model.book.start))" height="3" />
            <rect class="tl-frame" :x="frame.x1" y="1" :width="frame.x2 - frame.x1" :height="OVERVIEW_H - 6" data-testid="overview-frame" />
          </g>

          <!-- the axis: ticks in their era's tint, folds labelled with their length, the brushed span -->
          <g class="tl-axis" :transform="`translate(0 ${OVERVIEW_H})`">
            <rect class="tl-axis-bg" x="0" :y="ERA_H" :width="W" :height="AXIS_H - ERA_H" data-testid="axis" />
            <g v-for="tk in tickList" :key="tk.t">
              <line class="tl-tick" :x1="tk.x" :x2="tk.x" :y1="AXIS_H - 8" :y2="AXIS_H" />
              <text class="tl-tick-label" :class="tk.era ? `era-${tk.era.colour} era-tint` : ''" :x="tk.x" :y="AXIS_H - 12" text-anchor="middle" data-testid="tick-label">{{ numberText(tk.t) }}</text>
            </g>
            <g v-for="f in foldsShown" :key="`f-${f.t1}`" class="tl-fold" data-testid="fold">
              <rect :x="f.sx" :y="ERA_H" :width="f.w" :height="AXIS_H - ERA_H" />
              <text :x="f.sx + f.w / 2" :y="AXIS_H - 12" text-anchor="middle">{{ foldText(f.length) }}</text>
            </g>
          </g>
          <rect v-if="brush" class="tl-brush" :x="X(brush.from)" :y="OVERVIEW_H + ERA_H" :width="Math.max(2, X(brush.to) - X(brush.from))" :height="laneY.height - OVERVIEW_H - ERA_H" data-testid="brush" />
          <rect v-if="brushing" class="tl-brush live" :x="Math.min(brushing.x0, brushing.x1)" :y="OVERVIEW_H + ERA_H" :width="Math.abs(brushing.x1 - brushing.x0)" :height="laneY.height - OVERVIEW_H - ERA_H" />
          <g v-for="f in foldsShown" :key="`fl-${f.t1}`" class="tl-fold-lane">
            <rect :x="f.sx" :y="TOP" :width="f.w" :height="laneY.height - TOP - 10" />
          </g>

          <!-- lanes -->
          <g v-for="(l, li) in lanes" :key="l.key" class="tl-lane" :class="[`lane-${l.kind}`, { folded: folded.has(l.key) }]" :transform="`translate(0 ${laneY.ys[li]})`" :data-lane="l.key" :data-title="l.title" data-testid="lane">
            <line class="tl-lane-line" x1="0" :x2="W" :y1="folded.has(l.key) ? FOLDED_H / 2 : laneY.hs[li]! - 10" :y2="folded.has(l.key) ? FOLDED_H / 2 : laneY.hs[li]! - 10" />
            <template v-if="!folded.has(l.key)">
              <!-- the book's band; a character's life, places over time, homes; a faction's roles; an era's nested eras -->
              <rect v-if="l.kind === 'book' && bookBand" class="tl-book" :x="bookBand.x1" :y="laneY.hs[li]! - 18" :width="bookBand.x2 - bookBand.x1" height="10" data-testid="book-band"><title>the book</title></rect>
              <template v-for="(s, si) in l.kind === 'book' ? [] : l.segments" :key="si">
                <rect v-if="X(s.t2) > -20 && X(s.t) < W + 20" class="tl-seg" :class="[`tone-${s.tone}`, s.colour ? `era-${s.colour}` : '', s.fade ? `fade-${s.fade}` : '']" :x="Math.max(-20, X(s.t))" :y="s.tone === 'life' ? laneY.hs[li]! - 13 : s.tone === 'lives' ? laneY.hs[li]! - 22 : 16" :width="Math.max(3, Math.min(W + 20, X(s.t2)) - Math.max(-20, X(s.t)))" :height="s.tone === 'life' ? 6 : 8" data-testid="segment" :data-label="s.label" :data-from="s.t" :data-to="s.t2">
                  <title>{{ s.label }}</title>
                </rect>
                <text v-if="segLabels[li]?.[si]" class="tl-seg-label" :x="segLabels[li]![si]!.x" y="14">{{ segLabels[li]![si]!.text }}</text>
              </template>
              <!-- leaders from a mark up to its name in a higher row, under every name -->
              <g class="tl-leaders">
                <template v-for="(o, oi) in shown[li]" :key="`ld-${o.item.mark?.id ?? o.item.cluster!.id}`">
                  <line v-if="labelSpots[li]?.[oi]?.row" class="tl-leader" :class="{ dim: dimOutside(o.x) }" :x1="o.x" :x2="o.x" :y1="laneY.hs[li]! - 10 - (o.item.cluster ? 11 : 5)" :y2="laneY.hs[li]! - 16 - labelSpots[li]![oi]!.row * ROW_H" />
                </template>
              </g>
              <g v-for="(o, oi) in shown[li]" :key="o.item.mark?.id ?? o.item.cluster!.id" :transform="`translate(${o.x} ${laneY.hs[li]! - 10})`" :class="[o.item.cluster ? 'tl-cluster' : `tl-mark kind-${o.item.mark!.kind}`, { dim: dimOutside(o.x), focused: focusRing(li, oi), told: o.item.mark?.told }]"
                :data-testid="o.item.cluster ? 'cluster' : 'mark'" :data-label="o.item.mark?.label" :data-count="o.item.cluster?.marks.length"
                @pointerenter="(e) => enter(e, o.item)" @pointerleave="leave" @pointerdown="(e) => touchStart(e, o.item)" @pointerup="touchEnd" @click="!moved && openItem(o.item)" @dblclick.stop="o.item.cluster && openItem(o.item)">
                <title>{{ tipFor(o.item) }}</title>
                <template v-if="o.item.cluster">
                  <circle :r="Math.min(11, 6 + Math.sqrt(o.item.cluster.marks.length) / 2)" class="tl-cluster-dot" />
                  <text class="tl-cluster-count" text-anchor="middle" y="4">{{ o.item.cluster.marks.length }}</text>
                </template>
                <template v-else>
                  <rect v-if="o.item.mark!.t2 != null && !far" class="tl-span" :x="0" y="-4" :width="Math.max(4, X(o.item.mark!.t2!) - o.x)" height="8" />
                  <path v-if="o.item.mark!.kind === 'chapter'" class="tl-tick-mark" d="M0 -9 L0 4" />
                  <circle v-else :r="far ? 3 : 4.5" class="tl-dot" />
                </template>
                <text v-if="labelSpots[li]?.[oi]" class="tl-label" :class="{ 'tl-cluster-label': o.item.cluster }" :x="labelSpots[li]![oi]!.left ? -(o.item.cluster ? 14 : 7) : o.item.cluster ? 14 : 7" :y="-6 - labelSpots[li]![oi]!.row * ROW_H" :text-anchor="labelSpots[li]![oi]!.left ? 'end' : 'start'" data-testid="mark-label" :data-row="labelSpots[li]![oi]!.row">{{ labelSpots[li]![oi]!.text }}</text>
              </g>
            </template>
            <!-- the lane's title (and its counts when folded), how many of its own are outside time (listed below the
                 Timeline), fold and remove -->
            <g class="tl-lane-head">
              <rect x="0" y="0" :width="titleWidth(l) + (outsideNote(l) ? textWidth(outsideNote(l), FONT) + 12 : 0)" height="14" class="tl-lane-title-bg" />
              <text class="tl-lane-title" x="4" y="11" :data-testid="folded.has(l.key) ? 'lane-counts' : 'lane-title'" @click="l.kind !== 'events' && l.kind !== 'book' && toggleFold(l.key)">{{ titleText(l) }}</text>
              <text v-if="outsideNote(l)" class="tl-lane-outside" :x="titleWidth(l) + 4" y="11" data-testid="lane-outside">{{ outsideNote(l) }}<title>outside time: {{ laneOutside(l) }}</title></text>
            </g>
          </g>

          <!-- cause arrows (docs/SPEC.md §14.7): from cause to effect, curving above; planned and rumoured dashed -->
          <g v-if="arrows.length" class="tl-arrows" pointer-events="none">
            <defs>
              <marker id="tl-arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" class="tl-arrowhead" />
              </marker>
            </defs>
            <g v-for="a in arrows" :key="a.key" :opacity="a.opacity" data-testid="cause-arrow" :data-from="a.from" :data-to="a.to" :data-dashed="a.dashed ? 'yes' : 'no'">
              <path :d="a.d" class="tl-arrow" :class="{ dashed: a.dashed, before: a.before }" marker-end="url(#tl-arrowhead)" />
              <text v-if="a.before" class="tl-arrow-note" :x="a.mid.x" :y="a.mid.y" text-anchor="middle" data-testid="before-cause">before its cause</text>
            </g>
          </g>
          <g v-for="a in arrows" :key="`e-${a.key}`">
            <text v-for="e in a.edges" :key="e.name" class="tl-arrow-edge" :x="e.x < W / 2 ? 6 : W - 6" :y="e.y - 12" :text-anchor="e.x < W / 2 ? 'start' : 'end'" data-testid="arrow-edge" @click="panTo(e.t)">{{ e.x < W / 2 ? "← " : "" }}{{ e.name }}{{ e.x < W / 2 ? "" : " →" }}</text>
          </g>
        </svg>
        <div v-if="keptCard" class="qcard kept-card" data-testid="kept-card">
          <div class="qcard-head">
            <strong>{{ keptCard.name }}</strong>
            <button type="button" class="chip-x" aria-label="Let the arrows go" data-testid="let-go" @click="letGo">×</button>
          </div>
          <div class="qrow">
            <button v-if="!whole" type="button" class="qchip" @click="keepArrows(kept!, true)">Whole chain</button>
            <button v-else type="button" class="qchip" @click="keepArrows(kept!, false)">Direct causes only</button>
          </div>
          <div v-for="x in keptCard.notPlaced" :key="x.other" class="qcard-also">
            {{ x.reads }}: {{ x.name }} (not placed yet) ·
            <RouterLink :to="{ name: 'entity', params: { world: world!.slug, id: x.other } }">When…</RouterLink>
          </div>
        </div>
        <p v-if="!visibleTimes.length && cards.world === worldSlug" class="empty" data-testid="timeline-empty">
          {{ view === "history" ? "No history yet: nothing is set before the book." : "Nothing has a time yet. Give an event a time on its page, or a chapter on the manuscript list." }}
        </p>
      </div>
      <aside v-if="chartOpen" class="card timeline-chart" data-testid="timeline-chart">
        <div class="card-head">
          <h2>Chart</h2>
          <span class="small muted">{{ brush ? "as the span ends, with what changed across it" : "the end of the story; brush a span to follow it" }}</span>
          <RouterLink class="small" :to="{ name: 'chart', params: { world: world.slug }, query: { follow: '1' } }" data-testid="chart-page-link">Open the chart</RouterLink>
        </div>
        <ChartSpan :world="world.slug" :from="brush?.from ?? null" :to="brush?.to ?? null" :height="320" />
      </aside>
      </div>

      <div v-if="laneKeys.length" class="lane-list small">
        <span v-for="key2 in laneKeys" :key="key2" class="chip static">
          <button type="button" class="linkish" :data-testid="`fold-${key2}`" @click="toggleFold(key2)">{{ folded.has(key2) ? "▸" : "▾" }} {{ lanes.find((x) => x.key === key2)?.title ?? key2 }}</button>
          <button type="button" class="chip-x" :aria-label="`Remove the lane`" @click="removeLane(key2)">×</button>
        </span>
      </div>

      <section v-if="model.outside.length" class="card outside-strip" data-testid="outside-strip">
        <h2 class="small muted">Outside time</h2>
        <ul class="plain-list inline">
          <li v-for="o in model.outside" :key="o.id">
            <RouterLink v-if="o.entity" :to="{ name: 'entity', params: { world: world.slug, id: o.entity } }" class="kname k-event">{{ o.label }}</RouterLink>
            <RouterLink v-else :to="{ name: 'chapter', params: { world: world.slug, id: o.chapter } }">{{ o.label }}</RouterLink>
          </li>
        </ul>
      </section>

      <section v-if="brush" class="card in-span" data-testid="in-span">
        <div class="card-head">
          <h2>In this span</h2>
          <span class="small" data-testid="span-line">{{ spanLine }}</span>
          <button type="button" class="chip-x" aria-label="Clear the span" data-testid="clear-span" @click="clearBrush">×</button>
        </div>
        <div v-for="g in spanGroups" :key="g.value" class="span-group">
          <h3 class="small muted">{{ g.label }} ({{ g.marks.length }})</h3>
          <ul class="plain-list">
            <li v-for="m in g.marks" :key="m.id" data-testid="span-item">
              <a href="#" @click.prevent="openItem({ mark: m })">{{ m.label }}</a>
              <span class="muted small"> · {{ timeText({ time_at: m.t, time_approx: m.approx }, unit) }}</span>
            </li>
          </ul>
        </div>
        <p v-if="!spanMarks.length" class="muted small">Nothing in this span.</p>
      </section>

      <section v-if="model.unplaced.length" class="card unplaced" data-testid="unplaced">
        <h2 class="small muted">Not placed yet</h2>
        <ul class="rows">
          <li v-for="u in model.unplaced" :key="u.id">
            <RouterLink class="kname k-event grow" :to="{ name: 'entity', params: { world: world.slug, id: u.id } }">{{ u.name }}</RouterLink>
            <form class="actions" @submit.prevent="placeEvent(u.id)">
              <input v-model="whenDraft[u.id]" class="filter time-num" inputmode="decimal" :placeholder="`When… (${unit.unit})`" :aria-label="`When ${u.name} happens`" />
              <button class="btn btn-sm" type="submit">Set</button>
            </form>
          </li>
        </ul>
      </section>
    </template>

    <section v-else class="card told-view" data-testid="told">
      <ol class="rows told-rows">
        <li v-for="r in told.rows" :key="r.c.id" data-testid="told-row" :data-title="r.c.title">
          <span class="told-margin" :title="r.at === null ? 'outside time' : 'where it sits in happened order'">
            <span v-if="r.at !== null" class="told-dot" :class="{ jump: r.c.told_as }" :style="{ left: `${r.at * 100}%` }" data-testid="told-dot" :data-at="r.at" />
            <span v-else class="told-apart">outside</span>
          </span>
          <span class="grow">
            <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: r.c.id } }">{{ r.c.index + 1 }} · {{ r.c.title }}</RouterLink>
            <span v-if="r.c.told_as" class="pill told-as">{{ r.c.told_as }}</span>
            <span class="small" :class="r.era ? `era-${r.era.colour} era-tint` : 'muted'"> {{ whenOf(r.c) }}<template v-if="r.era"> · {{ r.era.name }}</template></span>
            <span v-if="r.told.length" class="small told-list" data-testid="told-in-chapter"> · told: {{ r.told.join(", ") }}</span>
            <span v-if="r.happens.length" class="small told-list"> · happens: {{ r.happens.join(", ") }}</span>
            <span v-if="r.life.length" class="small told-list"> · {{ r.life.join(", ") }}</span>
          </span>
        </li>
      </ol>
      <template v-if="told.notInBook.length">
        <h2 class="small muted">Not in the book yet</h2>
        <ul class="plain-list inline">
          <li v-for="e in told.notInBook" :key="e.id"><RouterLink class="kname k-event" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink><span v-if="chron?.notes?.[e.id]" class="muted small" data-testid="noted-count"> · noted in the Journal {{ chron.notes[e.id] === 1 ? "once" : `${chron.notes[e.id]} times` }}</span></li>
        </ul>
      </template>
    </section>
  </template>
</template>
