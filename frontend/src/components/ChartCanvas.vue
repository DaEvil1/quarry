<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { useCards } from "../world/cards";
import { holdsCount, shapePath, type ChartState, type Laid, type Layout } from "../world/chart";
import { ERA_COLOURS } from "../world/eras";
import { hideCard, showCard } from "../world/hovercard";

// The chart drawn (docs/SPEC.md §13.7): each place as its shape, nested in its container, with its name; routes as
// lines above the shapes; borders across containers as a short thick mark; who controls a place as a shade in the
// faction's colour (striped when two do); who is there as small dots. Wheel or pinch zooms around the pointer and
// dragging pans; zoomed out, a container folds to its name and how many places it holds. Dragging a place (a
// long-press first on the phone) pins it. Plain SVG; the layout comes worked out from the page.
const props = withDefaults(defineProps<{
  state: ChartState | null;
  layout: Layout | null;
  /** what the editor's card reads as of */
  point: string | null | { time: number };
  outlined?: Set<string>;
  focus?: string;
  editable?: boolean;
  height?: number;
}>(), { outlined: () => new Set(), focus: "", editable: true, height: 560 });
const emit = defineEmits<{ pin: [place: string, container: string | null, x: number, y: number]; open: [id: string] }>();
const cards = useCards();

// ---- the view box: fit, zoom, pan ----
const svg = ref<SVGSVGElement | null>(null);
const box = ref({ x: -300, y: -200, w: 600, h: 400 });
const width = ref(800);
let ro: ResizeObserver | null = null;
onMounted(() => {
  if (!svg.value) return;
  width.value = svg.value.clientWidth || 800;
  ro = new ResizeObserver(() => (width.value = svg.value?.clientWidth || width.value));
  ro.observe(svg.value);
});
onBeforeUnmount(() => {
  ro?.disconnect();
  hideCard(true);
});
/** pixels per unit of the chart */
const scale = computed(() => Math.min(width.value / box.value.w, props.height / box.value.h));
function fitTo(b: { x: number; y: number; w: number; h: number }, pad = 40) {
  const aspect = width.value / props.height;
  let w = b.w + pad * 2;
  let h = b.h + pad * 2;
  if (w / h < aspect) w = h * aspect;
  else h = w / aspect;
  box.value = { x: b.x + b.w / 2 - w / 2, y: b.y + b.h / 2 - h / 2, w, h };
}
function fit() {
  if (props.layout) fitTo(props.layout.bounds);
}
let fitted = "";
watch(() => [props.layout, props.focus, width.value] as const, () => {
  const l = props.layout;
  if (!l) return;
  const key = `${props.focus}|${width.value}|${l.laid.size}`;
  if (key === fitted) return;
  fitted = key;
  const f = props.focus ? l.laid.get(props.focus) : undefined;
  if (f) fitTo({ x: f.ax - f.r, y: f.ay - f.r, w: f.r * 2, h: f.r * 2 }, f.r * 0.6);
  else fit();
}, { immediate: true });
defineExpose({ fit });
const local = (e: { clientX: number; clientY: number }) => {
  const r = svg.value!.getBoundingClientRect();
  const s = scale.value;
  const ox = (r.width - box.value.w * s) / 2;
  const oy = (r.height - box.value.h * s) / 2;
  return { x: box.value.x + (e.clientX - r.left - ox) / s, y: box.value.y + (e.clientY - r.top - oy) / s };
};
function zoomAround(p: { x: number; y: number }, k: number) {
  const b = box.value;
  const w = Math.min(Math.max(b.w * k, 20), 40000);
  const f = w / b.w;
  box.value = { x: p.x - (p.x - b.x) * f, y: p.y - (p.y - b.y) * f, w, h: b.h * f };
}
function wheel(e: WheelEvent) {
  zoomAround(local(e), Math.pow(1.0015, e.deltaY));
}

// ---- pointers: pan, pinch, drag a place to pin it ----
const pointers = new Map<number, { x: number; y: number }>();
let pan: { x: number; y: number; bx: number; by: number } | null = null;
let pinch: { d: number; w: number; mid: { x: number; y: number } } | null = null;
const dragging = ref<{ id: string; dx: number; dy: number } | null>(null);
let dragStart: { id: string; x: number; y: number } | null = null;
let press = 0;
let moved = false;
function down(e: PointerEvent) {
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  moved = false;
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    pinch = { d: Math.hypot(a!.x - b!.x, a!.y - b!.y) || 1, w: box.value.w, mid: local({ clientX: (a!.x + b!.x) / 2, clientY: (a!.y + b!.y) / 2 }) };
    pan = null;
    dragStart = null;
    window.clearTimeout(press);
    return;
  }
  const place = (e.target as Element).closest<SVGGElement>("[data-place]")?.dataset.place;
  const start = local(e);
  if (place && props.editable) {
    // on the desk a place drags at once; on the phone a long-press first, so panning doesn't pin
    if (e.pointerType === "touch") press = window.setTimeout(() => ((dragStart = { id: place, ...start }), (pan = null)), 450);
    else dragStart = { id: place, ...start };
  }
  pan = { x: e.clientX, y: e.clientY, bx: box.value.x, by: box.value.y };
  if (dragStart) pan = null;
}
function move(e: PointerEvent) {
  if (!pointers.has(e.pointerId)) return;
  const prev = pointers.get(e.pointerId)!;
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (!moved && Math.hypot(e.clientX - prev.x, e.clientY - prev.y) > 0) {
    if (!dragStart) window.clearTimeout(press);
  }
  if (pinch && pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    const d = Math.hypot(a!.x - b!.x, a!.y - b!.y) || 1;
    const k = (pinch.w * (pinch.d / d)) / box.value.w;
    zoomAround(pinch.mid, k);
    return;
  }
  if (dragStart) {
    const p = local(e);
    const dx = p.x - dragStart.x;
    const dy = p.y - dragStart.y;
    if (!moved && Math.hypot(dx, dy) * scale.value > 4) {
      moved = true;
      svg.value?.setPointerCapture(e.pointerId);
      hideCard(true);
    }
    if (moved) dragging.value = { id: dragStart.id, dx, dy };
    return;
  }
  if (pan) {
    const s = scale.value;
    if (Math.hypot(e.clientX - pan.x, e.clientY - pan.y) > 4 && !moved) {
      moved = true;
      svg.value?.setPointerCapture(e.pointerId);
    }
    box.value = { ...box.value, x: pan.bx - (e.clientX - pan.x) / s, y: pan.by - (e.clientY - pan.y) / s };
  }
}
function up(e: PointerEvent) {
  pointers.delete(e.pointerId);
  window.clearTimeout(press);
  if (pointers.size < 2) pinch = null;
  const d = dragging.value;
  if (d && props.layout) {
    const l = props.layout.laid.get(d.id);
    if (l) emit("pin", d.id, props.state?.places.get(d.id)?.parent ?? null, l.x + d.dx, l.y + d.dy);
  }
  dragging.value = null;
  dragStart = null;
  pan = null;
}
function click(id: string) {
  if (moved) return;
  emit("open", id);
}

// ---- what is drawn: containers first, then what is inside, folded when too small on screen ----
// a container smaller than this on screen (its radius, in pixels) folds to its name and count
const FOLD_PX = 40;
interface Drawn {
  id: string;
  l: Laid;
  x: number;
  y: number;
  d: string;
  shape: string;
  name: string;
  container: boolean;
  folded: boolean;
  count: number;
  control: string[];
  here: string[];
  untyped: boolean;
}
const shiftOf = (id: string) => {
  // a place being dragged moves with everything inside it
  const d = dragging.value;
  if (!d || !props.state) return { x: 0, y: 0 };
  let p: string | null = id;
  while (p) {
    if (p === d.id) return { x: d.dx, y: d.dy };
    p = props.state.places.get(p)?.parent ?? null;
  }
  return { x: 0, y: 0 };
};
const drawn = computed<Drawn[]>(() => {
  const s = props.state;
  const lay = props.layout;
  if (!s || !lay) return [];
  const out: Drawn[] = [];
  const k = scale.value;
  const walk = (id: string) => {
    const l = lay.laid.get(id);
    const p = s.places.get(id);
    if (!l || !p) return;
    const kids = p.children.filter((c) => lay.laid.has(c));
    const folded = kids.length > 0 && l.r * k < FOLD_PX;
    const sh = shiftOf(id);
    out.push({
      id, l, x: l.ax + sh.x, y: l.ay + sh.y, d: shapePath(p.shape, l.r, kids.length > 0), shape: p.shape, name: p.name, container: kids.length > 0 && !folded, folded,
      count: folded ? holdsCount(s, id) : 0, control: s.control.get(id) ?? [], here: s.here.get(id) ?? [], untyped: p.shape === "none",
    });
    if (!folded) for (const c of kids) walk(c);
  };
  for (const r of s.roots) walk(r);
  return out;
});
const at = computed(() => new Map(drawn.value.map((d) => [d.id, d])));
/** a place's position on the chart: its own, or the folded container it is drawn inside */
const posOf = (id: string): Drawn | undefined => {
  let p: string | null = id;
  while (p) {
    const d = at.value.get(p);
    if (d) return d;
    p = props.state?.places.get(p)?.parent ?? null;
  }
  return undefined;
};
const edgePoint = (a: Drawn, b: Drawn) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const n = Math.hypot(dx, dy) || 1;
  return { x: a.x + (dx / n) * a.l.r, y: a.y + (dy / n) * a.l.r };
};
const routes = computed(() =>
  (props.state?.routes ?? []).map((r, i) => {
    const a = posOf(r.a);
    const b = posOf(r.b);
    if (!a || !b || a === b) return null;
    const p = edgePoint(a, b);
    const q = edgePoint(b, a);
    return { key: `${r.a}-${r.b}-${i}`, kind: r.kind, planned: r.standing !== "canon", x1: p.x, y1: p.y, x2: q.x, y2: q.y, title: `${cards.byId.get(r.a)?.name ?? ""} – ${cards.byId.get(r.b)?.name ?? ""}` };
  }).filter((x): x is NonNullable<typeof x> => !!x),
);
// borders across containers: a short thick mark at the nearest edges
const borderMarks = computed(() =>
  (props.state?.borders ?? []).map((b, i) => {
    const pa = props.state!.places.get(b.a)?.parent ?? null;
    const pb = props.state!.places.get(b.b)?.parent ?? null;
    const a = posOf(b.a);
    const c = posOf(b.b);
    if (!a || !c || a === c) return null;
    const p = edgePoint(a, c);
    const q = edgePoint(c, a);
    // in the same container they are laid out touching: mark only where there is a gap
    if (pa === pb && Math.hypot(p.x - q.x, p.y - q.y) < 6) return null;
    const mx = (p.x + q.x) / 2;
    const my = (p.y + q.y) / 2;
    const len = Math.min(Math.hypot(p.x - q.x, p.y - q.y) / 2 + 6, 26);
    const n = Math.hypot(q.x - p.x, q.y - p.y) || 1;
    const ux = (q.x - p.x) / n;
    const uy = (q.y - p.y) / n;
    return { key: `${b.a}-${b.b}-${i}`, x1: mx - ux * len, y1: my - uy * len, x2: mx + ux * len, y2: my + uy * len };
  }).filter((x): x is NonNullable<typeof x> => !!x),
);
const colourOf = computed(() => new Map((props.state?.factions ?? []).map((f, i) => [f, ERA_COLOURS[i % ERA_COLOURS.length]!])));
const legend = computed(() => (props.state?.factions ?? []).map((f) => ({ id: f, name: cards.byId.get(f)?.name ?? "?", colour: colourOf.value.get(f)! })));
const stripes = computed(() => {
  const out = new Map<string, string[]>();
  for (const d of drawn.value) if (d.control.length > 1) out.set(d.control.map((f) => colourOf.value.get(f)).join("-"), d.control.map((f) => colourOf.value.get(f)!));
  return [...out.entries()].map(([id, colours]) => ({ id: `stripe-${id}`, colours }));
});
const shade = (d: Drawn) => (d.control.length > 1 ? `url(#stripe-${d.control.map((f) => colourOf.value.get(f)).join("-")})` : undefined);
const dots = (d: Drawn) => {
  const n = d.here.length;
  return d.here.map((id, i) => ({ id, name: cards.byId.get(id)?.name ?? "", x: (i - (n - 1) / 2) * 9, y: d.container ? d.l.r - 12 : d.l.r * 0.35 }));
};
// names stay about 11 px on screen at any zoom
const fontFor = (_d: Drawn) => 11.5 / scale.value;

// ---- the editor's card on resting, as of the chosen point ----
function enter(e: PointerEvent, id: string) {
  if (dragging.value) return;
  const c = cards.byId.get(id);
  const now = cards.asOf(c, props.point);
  const p = props.state?.places.get(id);
  const notes = [p?.shape === "none" ? "no type" : "", p?.alsoIn.length ? `also inside ${p.alsoIn.map((x) => cards.byId.get(x)?.name).join(", ")}` : ""].filter(Boolean).join(" · ");
  const card = now && notes ? { ...now, summary: now.summary ? `${now.summary} · ${notes}` : notes } : now;
  showCard(e.currentTarget as HTMLElement, card, () => emit("open", id), 350, (kind, label) => cards.several(kind, label));
}
</script>

<template>
  <div class="chart-wrap">
    <svg
      ref="svg"
      class="chart"
      :viewBox="`${box.x} ${box.y} ${box.w} ${box.h}`"
      :height="height"
      preserveAspectRatio="xMidYMid meet"
      role="application"
      aria-label="The chart: drag to move, scroll or pinch to zoom, drag a place to pin it"
      data-testid="chart"
      @wheel.prevent="wheel"
      @pointerdown="down"
      @pointermove="move"
      @pointerup="up"
      @pointercancel="up"
    >
      <defs>
        <pattern v-for="s in stripes" :id="s.id" :key="s.id" patternUnits="userSpaceOnUse" width="12" height="12" patternTransform="rotate(45)">
          <rect v-for="(c, i) in s.colours" :key="i" :class="`era-${c} chart-stripe`" :x="(i * 12) / s.colours.length" y="0" :width="12 / s.colours.length" height="12" />
        </pattern>
      </defs>
      <g
        v-for="d in drawn"
        :key="d.id"
        class="chart-place"
        :class="[`shape-${d.shape}`, { container: d.container, folded: d.folded, untyped: d.untyped, outlined: outlined.has(d.id), pinned: d.l.pinned, focus: focus === d.id }]"
        :style="{ transform: `translate(${d.x}px, ${d.y}px)` }"
        :data-place="d.id"
        :data-name="d.name"
        :data-shape="d.shape"
        :data-x="Math.round(d.x)"
        :data-y="Math.round(d.y)"
        :data-r="Math.round(d.l.r)"
        data-testid="chart-place"
        @pointerenter="(e) => enter(e, d.id)"
        @pointerleave="hideCard()"
        @click="click(d.id)"
      >
        <path class="chart-shape" :d="d.d" />
        <path v-if="d.control.length === 1" class="chart-control" :class="`era-${colourOf.get(d.control[0]!)}`" :d="d.d" data-testid="chart-control" :data-faction="d.control[0]" />
        <path v-else-if="d.control.length > 1" class="chart-control striped" :d="d.d" :fill="shade(d)" data-testid="chart-control" :data-faction="d.control.join(',')" />
        <text class="chart-name" :y="d.container ? -d.l.r + 4 + fontFor(d) : d.folded ? 4 : d.l.r + fontFor(d) + 2" text-anchor="middle" :style="{ fontSize: `${fontFor(d)}px` }">
          {{ d.folded ? `${d.name} · ${d.count} ${d.count === 1 ? "place" : "places"}` : d.name }}
        </text>
        <circle v-for="w in dots(d)" :key="w.id" class="chart-here" :cx="w.x" :cy="w.y" r="3.2" data-testid="chart-here" :data-who="w.name"><title>{{ w.name }}</title></circle>
      </g>
      <line v-for="b in borderMarks" :key="b.key" class="chart-border" :x1="b.x1" :y1="b.y1" :x2="b.x2" :y2="b.y2" data-testid="chart-border" />
      <line v-for="r in routes" :key="r.key" class="chart-route" :class="[r.kind, { planned: r.planned }]" :x1="r.x1" :y1="r.y1" :x2="r.x2" :y2="r.y2" :data-testid="`chart-${r.kind}`"><title>{{ r.title }}</title></line>
    </svg>
    <div v-if="legend.length" class="chart-legend small" data-testid="chart-legend">
      <span v-for="f in legend" :key="f.id" class="chart-key"><span class="chart-swatch" :class="`era-${f.colour}`" />{{ f.name }}</span>
    </div>
  </div>
</template>
