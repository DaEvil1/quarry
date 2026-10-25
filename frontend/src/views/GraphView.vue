<script setup lang="ts">
import { forceCollide, forceLink, forceManyBody, forceRadial, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import { computed, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get } from "../api";
import EntityPicker from "../components/EntityPicker.vue";
import FamilyTree from "../components/FamilyTree.vue";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type EntityRef } from "../types";
import { useCards } from "../world/cards";
import { familyLinks } from "../world/family";
import { clusters, neighbourhood, placeTree, visibleLinks, type GraphData, type Link, type PlaceNode } from "../world/graph";
import { norm } from "../world/labels";
import { speciesColours } from "../world/species";
import NotFoundView from "./NotFoundView.vue";

// The world as a graph: entries and their relationships at a point in the story, centred on one entry or all of
// them, coloured by kind or by cluster; and the places nested inside each other with who is where.
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const tab = computed(() => (route.query.view === "places" ? "places" : route.query.view === "family" ? "family" : "graph"));
const data = shallowRef<GraphData | null>(null);
const withCo = ref(false);
const error = ref("");

// filters (the as-of chapter and the centre are in the address)
const asOfId = computed(() => (typeof route.query.asof === "string" ? route.query.asof : ""));
const asOf = computed(() => cards.indexOf(asOfId.value || null) ?? null);
const centre = computed(() => (typeof route.query.centre === "string" ? route.query.centre : ""));
const depth = ref(2);
const kinds = ref(new Set<string>(ENTITY_KINDS.map((k) => k.value)));
const standings = ref(new Set<string>(["canon", "planned", "rumour"]));
const typeId = ref("");
const coMin = ref(0);
const colourBy = ref<"kind" | "cluster" | "species">("kind");
const showLoners = ref(false);
const setQuery = (q: Record<string, string | undefined>) => void router.replace({ query: { ...route.query, ...q } });

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    data.value = await get<GraphData>(`/api/worlds/${encodeURIComponent(worldSlug.value)}/graph${withCo.value ? "?co=true" : ""}`);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(worldSlug, (w) => {
  void cards.load(w, true);
  void load();
}, { immediate: true });
watch(coMin, (n) => {
  if (n > 0 && !withCo.value) {
    withCo.value = true;
    void load();
  }
});

// the project filter (docs/SPEC.md §12.4): the world's entries and that book's own, not other books' own entries
const projects = computed(() => world.value?.projects ?? []);
const book = computed(() => (typeof route.query.book === "string" && projects.value.some((p) => p.slug === route.query.book) ? route.query.book : ""));
const outside = computed(() => new Set(book.value ? (data.value?.nodes ?? []).filter((n) => n.project && n.project !== book.value).map((n) => n.id) : []));
const kindsPresent = computed(() => ENTITY_KINDS.filter((k) => data.value?.nodes.some((n) => n.kind === k.value)));
const usedTypes = computed(() => {
  const used = new Set(data.value?.edges.map((e) => e.type_id));
  return (data.value?.types ?? []).filter((t) => used.has(t.id));
});
function toggle(which: "kinds" | "standings", v: string) {
  const set = which === "kinds" ? kinds : standings;
  const next = new Set(set.value);
  if (next.has(v)) next.delete(v);
  else next.add(v);
  set.value = next;
}
const timelineGroups = computed(() => {
  const out: { name: string; chapters: typeof cards.timeline }[] = [];
  for (const c of cards.timeline) {
    const last = out[out.length - 1];
    if (last?.name === c.project_name) last.chapters.push(c);
    else out.push({ name: c.project_name, chapters: [c] });
  }
  return out;
});

// ---- what is shown ----
const links = computed<Link[]>(() =>
  data.value
    ? visibleLinks(outside.value.size ? { ...data.value, nodes: data.value.nodes.filter((n) => !outside.value.has(n.id)), edges: data.value.edges.filter((e) => !outside.value.has(e.a) && !outside.value.has(e.b)), cooccurrence: data.value.cooccurrence.filter((c) => !outside.value.has(c.a) && !outside.value.has(c.b)) } : data.value, {
        asOf: asOf.value,
        indexOf: cards.indexOf,
        kinds: kinds.value,
        standings: standings.value,
        typeIds: typeId.value ? new Set([typeId.value]) : new Set(),
        coMin: coMin.value,
      })
    : [],
);
const near = computed(() => (centre.value ? neighbourhood(links.value, centre.value, depth.value) : null));
const shownLinks = computed(() => (near.value ? links.value.filter((l) => near.value!.has(l.a) && near.value!.has(l.b)) : links.value));
const shownNodes = computed(() => {
  const d = data.value;
  if (!d) return [];
  const linked = new Set(shownLinks.value.flatMap((l) => [l.a, l.b]));
  return d.nodes.filter((n) => kinds.value.has(n.kind) && !outside.value.has(n.id) && (near.value ? near.value.has(n.id) : linked.has(n.id) || showLoners.value));
});
const loners = computed(() => {
  const linked = new Set(links.value.flatMap((l) => [l.a, l.b]));
  return (data.value?.nodes ?? []).filter((n) => kinds.value.has(n.kind) && !linked.has(n.id)).length;
});
// only worked out when colouring by cluster: it's the slowest step for a big world
const clusterOf = computed(() => (colourBy.value === "cluster" ? clusters(shownNodes.value.map((n) => n.id), shownLinks.value) : new Map<string, number>()));
const clusterCount = computed(() => new Set([...clusterOf.value.values()].filter((c) => c >= 0)).size);
const degree = computed(() => {
  const d = new Map<string, number>();
  for (const l of shownLinks.value) for (const x of [l.a, l.b]) d.set(x, (d.get(x) ?? 0) + 1);
  return d;
});

// ---- layout (d3-force, run to rest before drawing, so nothing jiggles) ----
interface P extends SimulationNodeDatum {
  id: string;
}
const pos = shallowRef(new Map<string, { x: number; y: number }>());
let laidOut = "";
watch([shownNodes, shownLinks, near], () => {
  // the same picture (a filter that changed nothing, data that hasn't arrived yet): keep it
  const key = `${centre.value}|${depth.value}|${shownNodes.value.map((n) => n.id).join(",")}|${shownLinks.value.map((l) => `${l.a}-${l.b}`).join(",")}`;
  if (key === laidOut) return;
  laidOut = key;
  let placed = 0;
  const nodes: P[] = shownNodes.value.map((n) => {
    const old = pos.value.get(n.id);
    if (old) placed++;
    return { id: n.id, x: old?.x, y: old?.y };
  });
  // mostly where they were: settle from there instead of starting over
  const warm = !near.value && nodes.length > 0 && placed / nodes.length > 0.8;
  const sim = forceSimulation(nodes)
    .force("link", forceLink<P, { source: string; target: string; kind: string }>(shownLinks.value.map((l) => ({ source: l.a, target: l.b, kind: l.kind })))
      .id((d) => d.id)
      .distance((l) => (l.kind === "co" ? 110 : 70))
      .strength((l) => (l.kind === "co" ? 0.2 : 0.6)))
    .force("charge", forceManyBody().strength(-220).distanceMax(500))
    .force("collide", forceCollide(22))
    .stop();
  if (near.value) {
    const c = nodes.find((n) => n.id === centre.value);
    if (c) (c.fx = 0), (c.fy = 0);
    sim.force("radial", forceRadial<P>((d) => (near.value!.get(d.id) ?? 2) * 160).strength(0.9));
  } else {
    sim.force("x", forceX(0).strength(0.05)).force("y", forceY(0).strength(0.05));
  }
  if (warm) sim.alpha(0.25);
  sim.tick(warm ? 80 : Math.min(300, 100 + nodes.length));
  pos.value = new Map(nodes.map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]));
  fit();
}, { immediate: true });

// ---- view box: fit, zoom with the wheel, pan by dragging ----
const box = ref({ x: -400, y: -300, w: 800, h: 600 });
function fit() {
  const ps = [...pos.value.values()];
  if (!ps.length) return;
  const xs = ps.map((p) => p.x);
  const ys = ps.map((p) => p.y);
  const pad = 80;
  const x = Math.min(...xs) - pad;
  const y = Math.min(...ys) - pad;
  box.value = { x, y, w: Math.max(400, Math.max(...xs) + pad - x), h: Math.max(300, Math.max(...ys) + pad - y) };
}
const svg = ref<SVGSVGElement | null>(null);
function wheel(e: WheelEvent) {
  const s = svg.value;
  if (!s) return;
  const r = s.getBoundingClientRect();
  const b = box.value;
  const scale = Math.max(b.w / r.width, b.h / r.height);
  const k = e.deltaY > 0 ? 1.15 : 1 / 1.15;
  // keep the point under the pointer where it is
  const px = b.x + (e.clientX - r.left - (r.width - b.w / scale) / 2) * scale;
  const py = b.y + (e.clientY - r.top - (r.height - b.h / scale) / 2) * scale;
  box.value = { x: px - (px - b.x) * k, y: py - (py - b.y) * k, w: b.w * k, h: b.h * k };
}
let drag: { x: number; y: number; bx: number; by: number } | null = null;
function down(e: PointerEvent) {
  if ((e.target as Element).closest(".gnode")) return;
  drag = { x: e.clientX, y: e.clientY, bx: box.value.x, by: box.value.y };
  (e.currentTarget as Element).setPointerCapture(e.pointerId);
}
function move(e: PointerEvent) {
  if (!drag || !svg.value) return;
  const r = svg.value.getBoundingClientRect();
  const scale = Math.max(box.value.w / r.width, box.value.h / r.height);
  box.value = { ...box.value, x: drag.bx - (e.clientX - drag.x) * scale, y: drag.by - (e.clientY - drag.y) * scale };
}
const up = () => (drag = null);

// ---- drawing ----
const hover = ref<string | null>(null);
const nodeById = computed(() => new Map((data.value?.nodes ?? []).map((n) => [n.id, n])));
const hoverNear = computed(() => (hover.value ? neighbourhood(shownLinks.value, hover.value, 1) : null));
const showLabel = (id: string) =>
  shownNodes.value.length <= 70 || id === hover.value || (near.value?.get(id) ?? 9) <= 1 || (degree.value.get(id) ?? 0) >= 4 || !!hoverNear.value?.has(id);
// colour by species: characters take their species' colour as of the graph's chapter (docs/SPEC.md §13.3)
const bySpecies = computed(() => (colourBy.value === "species" && data.value ? speciesColours(data.value, asOf.value, cards.indexOf) : null));
const speciesColour = computed(() => new Map((bySpecies.value?.legend ?? []).map((s) => [s.id, s.colour])));
const colour = (id: string) => {
  if (colourBy.value === "kind") return `var(--k-${nodeById.value.get(id)?.kind ?? "other"})`;
  if (colourBy.value === "species") {
    const s = nodeById.value.get(id)?.kind === "species" ? id : bySpecies.value?.of.get(id);
    return (s && speciesColour.value.get(s)) || "var(--muted)";
  }
  const c = clusterOf.value.get(id) ?? -1;
  return c < 0 ? "var(--muted)" : `hsl(${(c * 137.5 + 25) % 360} 60% 50%)`;
};
const dim = (id: string) => !!hoverNear.value && !hoverNear.value.has(id);
const linkText = (l: Link) => {
  const a = nodeById.value.get(l.a)?.name;
  const b = nodeById.value.get(l.b)?.name;
  return l.kind === "co" ? `${a} and ${b}: ${l.label}` : `${a} ${l.label} ${b}${l.standing && l.standing !== "canon" ? ` (${l.standing})` : ""}`;
};

function pick(id: string) {
  setQuery({ centre: id === centre.value ? undefined : id });
}
const openEntry = (id: string) => void router.push({ name: "entity", params: { world: worldSlug.value, id } });

// the centre's circle, in words: direct links, and who is reached through whom
const circle = computed(() => {
  if (!near.value || !centre.value) return null;
  const direct: { who: EntityRef; how: string[] }[] = [];
  const second: { who: EntityRef; via: string[] }[] = [];
  const name = (id: string) => nodeById.value.get(id)!;
  for (const [id, d] of near.value) {
    if (d === 1) {
      const how = shownLinks.value
        .filter((l) => (l.a === centre.value && l.b === id) || (l.b === centre.value && l.a === id))
        .map((l) => (l.kind === "co" ? "named together" : l.a === centre.value ? l.label : (data.value?.edges.find((e) => e.a === l.a && e.b === l.b && e.label === l.label)?.reverse_label ?? l.label)));
      direct.push({ who: name(id), how });
    } else if (d === 2) {
      const via = [...near.value]
        .filter(([m, dm]) => dm === 1 && shownLinks.value.some((l) => (l.a === m && l.b === id) || (l.b === m && l.a === id)))
        .map(([m]) => name(m).name);
      second.push({ who: name(id), via });
    }
  }
  const byName = (x: { who: EntityRef }, y: { who: EntityRef }) => x.who.name.localeCompare(y.who.name);
  return { direct: direct.sort(byName), second: second.sort(byName) };
});

// ---- the family (docs/SPEC.md §12.2): as of the chosen chapter, with the standings shown ----
const family = computed(() => (data.value ? familyLinks(data.value, { asOf: asOf.value, indexOf: cards.indexOf, standings: standings.value }) : []));
// the tab's own picker: everyone in a family (any time in the story)
const inFamilies = computed(() => {
  const all = data.value ? familyLinks(data.value, { asOf: null, indexOf: cards.indexOf, standings: new Set(["canon", "planned", "rumour"]) }) : [];
  const ids = new Set(all.flatMap((l) => [l.a, l.b]));
  return cards.names.filter((n) => ids.has(n.id));
});
const DEAD = /\b(dead|deceased|died|killed|slain|murdered)\b/i;
/** A † for someone whose status is dead as of the chosen chapter (else at the end of the story). */
function dead(id: string): boolean {
  const at = asOfId.value || cards.timeline[cards.timeline.length - 1]?.id || null;
  const c = cards.asOf(cards.byId.get(id), at);
  return !!c?.facts.some((f) => norm(f.label) === "status" && DEAD.test(f.value));
}

// ---- places ----
const places = computed<PlaceNode[]>(() => (data.value ? placeTree(data.value, asOf.value, cards.indexOf, asOfId.value || null) : []));
const flatPlaces = computed(() => {
  const out: { node: PlaceNode; depth: number }[] = [];
  const walk = (xs: PlaceNode[], d: number) => {
    for (const x of xs) {
      out.push({ node: x, depth: d });
      walk(x.children, d + 1);
    }
  };
  walk(places.value, 0);
  return out;
});
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>{{ tab === "places" ? "Places" : tab === "family" ? "Family" : "Graph" }}</h1>
      </div>
      <div class="actions tabs">
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': tab === 'graph' }" @click="setQuery({ view: undefined })">Relationships</button>
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': tab === 'places' }" data-testid="tab-places" @click="setQuery({ view: 'places' })">Places</button>
        <button type="button" class="btn btn-sm" :class="{ 'btn-primary': tab === 'family' }" data-testid="tab-family" @click="setQuery({ view: 'family' })">Family</button>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <div class="toolbar graph-tools">
      <label v-if="cards.timeline.length" class="small muted">As of
        <select class="filter" :value="asOfId" data-testid="graph-as-of" @change="setQuery({ asof: ($event.target as HTMLSelectElement).value || undefined })">
          <option value="">the whole story</option>
          <optgroup v-for="p in timelineGroups" :key="p.name" :label="p.name">
            <option v-for="c in p.chapters" :key="c.id" :value="c.id">{{ c.title }}</option>
          </optgroup>
        </select>
      </label>
      <label v-if="tab === 'graph' && projects.length > 1" class="small muted">Book
        <select class="filter" :value="book" data-testid="graph-book" @change="setQuery({ book: ($event.target as HTMLSelectElement).value || undefined })">
          <option value="">every book</option>
          <option v-for="p in projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
      </label>
      <template v-if="tab === 'family'">
        <span v-for="s in ['canon', 'planned', 'rumour']" :key="s" class="chip static">
          <label><input type="checkbox" :checked="standings.has(s)" @change="toggle('standings', s)" /> {{ s }}</label>
        </span>
      </template>
      <template v-if="tab === 'graph'">
        <label class="small muted">Colour by
          <select v-model="colourBy" class="filter">
            <option value="kind">kind</option>
            <option value="cluster">cluster</option>
            <option value="species">species</option>
          </select>
        </label>
        <label class="small muted">Named together
          <select v-model.number="coMin" class="filter" data-testid="co-min">
            <option :value="0">not shown</option>
            <option :value="1">in 1+ paragraphs</option>
            <option :value="3">in 3+ paragraphs</option>
            <option :value="6">in 6+ paragraphs</option>
          </select>
        </label>
        <select v-model="typeId" class="filter" aria-label="Kind of relationship">
          <option value="">every kind of relationship</option>
          <option v-for="t in usedTypes" :key="t.id" :value="t.id">{{ t.label }}</option>
        </select>
      </template>
    </div>

    <template v-if="tab === 'graph'">
      <details class="graph-filters">
        <summary class="small">
          Show: {{ kinds.size >= kindsPresent.length ? "every kind" : kindsPresent.filter((k) => kinds.has(k.value)).map((k) => k.plural.toLowerCase()).join(", ") || "nothing" }}
          · {{ standings.size === 3 ? "canon, planned and rumour" : [...standings].join(", ") || "no standing" }}
        </summary>
        <div class="toolbar graph-tools">
          <span v-for="k in kindsPresent" :key="k.value" class="chip static" :class="`k-${k.value}`">
            <label><input type="checkbox" :checked="kinds.has(k.value)" @change="toggle('kinds', k.value)" /> <span class="kname">{{ k.plural }}</span></label>
          </span>
          <span v-for="s in ['canon', 'planned', 'rumour']" :key="s" class="chip static">
            <label><input type="checkbox" :checked="standings.has(s)" @change="toggle('standings', s)" /> {{ s }}</label>
          </span>
          <label v-if="!centre && loners" class="small muted"><input v-model="showLoners" type="checkbox" /> {{ loners }} without links</label>
        </div>
      </details>

      <div class="graph-layout">
        <section class="card graph-card">
          <div class="graph-head">
            <div v-if="!centre" class="grow centre-pick">
              <EntityPicker :entities="cards.names" placeholder="Centre on…" @pick="(e) => pick(e.id)" @cancel="() => {}" />
            </div>
            <template v-else>
              <span class="grow">
                Centred on <strong class="kname" :class="`k-${nodeById.get(centre)?.kind}`">{{ nodeById.get(centre)?.name }}</strong>
              </span>
              <select v-model.number="depth" class="filter" aria-label="How far">
                <option :value="1">direct links</option>
                <option :value="2">and one step further</option>
              </select>
              <button type="button" class="btn btn-sm" @click="setQuery({ centre: undefined })">Everyone</button>
            </template>
            <span v-if="colourBy === 'cluster'" class="muted small" data-testid="cluster-count">{{ clusterCount }} cluster{{ clusterCount === 1 ? "" : "s" }}</span>
            <span v-if="bySpecies" class="small species-legend" data-testid="species-legend">
              <span v-for="s in bySpecies.legend" :key="s.id" class="legend-item"><span class="legend-dot" :style="{ background: s.colour ?? 'var(--muted)' }" />{{ s.name }} ({{ s.count }})</span>
              <span class="legend-item muted"><span class="legend-dot" style="background: var(--muted)" />no species</span>
            </span>
            <button type="button" class="btn btn-sm" @click="fit">Fit</button>
          </div>
          <p v-if="!centre && shownNodes.length > 120" class="muted small graph-hint">
            {{ shownNodes.length }} entries at once. Centre on someone (above, or click a dot) to see their circle; scroll to zoom, drag to move.
          </p>
          <svg
            v-if="shownNodes.length"
            ref="svg"
            class="graph"
            :viewBox="`${box.x} ${box.y} ${box.w} ${box.h}`"
            preserveAspectRatio="xMidYMid meet"
            data-testid="graph"
            @wheel.prevent="wheel"
            @pointerdown="down"
            @pointermove="move"
            @pointerup="up"
            @pointercancel="up"
          >
            <g class="glinks">
              <line
                v-for="(l, i) in shownLinks"
                :key="i"
                :x1="pos.get(l.a)?.x"
                :y1="pos.get(l.a)?.y"
                :x2="pos.get(l.b)?.x"
                :y2="pos.get(l.b)?.y"
                :class="[l.kind, l.standing, { dim: dim(l.a) || dim(l.b) }]"
                :stroke-width="l.kind === 'co' ? 1 + l.weight : 1.6"
              >
                <title>{{ linkText(l) }}</title>
              </line>
            </g>
            <g
              v-for="n in shownNodes"
              :key="n.id"
              class="gnode"
              :class="{ dim: dim(n.id), centre: n.id === centre }"
              :transform="`translate(${pos.get(n.id)?.x ?? 0} ${pos.get(n.id)?.y ?? 0})`"
              :data-name="n.name"
              :data-cluster="clusterOf.get(n.id)"
              @mouseenter="hover = n.id"
              @mouseleave="hover = null"
              @click="pick(n.id)"
              @dblclick="openEntry(n.id)"
            >
              <title>{{ n.name }}{{ n.summary ? ` — ${n.summary}` : "" }} (click to centre, double-click to open)</title>
              <circle :r="n.id === centre ? 11 : 6 + Math.min(5, degree.get(n.id) ?? 0)" :fill="colour(n.id)" :data-fill="colour(n.id)" />
              <text v-if="showLabel(n.id)" y="-12" text-anchor="middle">{{ n.name }}</text>
            </g>
          </svg>
          <p v-else-if="data" class="empty">
            {{ data.edges.length ? "Nothing matches these filters." : "No relationships recorded yet. Add them on an entry's page, or from a name's card in a chapter." }}
          </p>
        </section>

        <aside v-if="circle" class="card circle" data-testid="circle">
          <h3 class="small muted">Directly</h3>
          <ul class="plain-list" data-testid="circle-direct">
            <li v-for="x in circle.direct" :key="x.who.id" :class="`k-${x.who.kind}`">
              <a href="#" class="kname" @click.prevent="pick(x.who.id)">{{ x.who.name }}</a>
              <span class="muted small"> {{ x.how.join(", ") }}</span>
            </li>
            <li v-if="!circle.direct.length" class="muted small">No one.</li>
          </ul>
          <template v-if="depth > 1">
            <h3 class="small muted">Through one other</h3>
            <ul class="plain-list" data-testid="circle-second">
              <li v-for="x in circle.second" :key="x.who.id" :class="`k-${x.who.kind}`">
                <a href="#" class="kname" @click.prevent="pick(x.who.id)">{{ x.who.name }}</a>
                <span class="muted small"> via {{ x.via.join(", ") }}</span>
              </li>
              <li v-if="!circle.second.length" class="muted small">No one.</li>
            </ul>
          </template>
          <RouterLink class="small" :to="{ name: 'entity', params: { world: world.slug, id: centre }, query: asOfId ? { asof: asOfId } : {} }">Open the entry</RouterLink>
        </aside>
      </div>
    </template>

    <section v-else-if="tab === 'family'" class="card family-card" data-testid="family">
      <div class="graph-head">
        <span v-if="centre && nodeById.get(centre)" class="grow">
          Centred on <strong class="kname k-character">{{ nodeById.get(centre)?.name }}</strong>
        </span>
        <div class="grow centre-pick" :class="{ narrow: centre }">
          <EntityPicker :entities="inFamilies" :placeholder="centre ? 'Someone else…' : 'Whose family?'" @pick="(e) => setQuery({ centre: e.id })" @cancel="() => {}" />
        </div>
        <RouterLink v-if="centre" class="btn btn-sm" :to="{ name: 'entity', params: { world: world.slug, id: centre }, query: asOfId ? { asof: asOfId } : {} }">Open the entry</RouterLink>
      </div>
      <FamilyTree v-if="data && centre" :world="world.slug" :data="data" :links="family" :centre="centre" :dead="dead" @centre="(id) => setQuery({ centre: id })" />
      <p v-else-if="data" class="empty">{{ inFamilies.length ? "Pick someone to see their family." : "No parents, children or marriages recorded yet." }}</p>
    </section>

    <section v-else class="card" data-testid="place-tree">
      <p v-if="data && !flatPlaces.length" class="empty">No places in the bible yet.</p>
      <ul class="rows place-tree">
        <li v-for="{ node, depth: d } in flatPlaces" :key="node.id" :style="{ paddingLeft: `${d * 22}px` }" :data-testid="`place-${node.name}`">
          <span class="k-place"><span v-if="d" class="muted">└ </span><RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: node.id } }">{{ node.name }}</RouterLink></span>
          <span v-for="g in node.people" :key="g.label" class="small">
            <span class="muted">{{ g.label }}: </span>
            <template v-for="(w, i) in g.who" :key="w.id"><span v-if="i" class="muted">, </span><RouterLink class="kname" :class="`k-${w.kind}`" :to="{ name: 'entity', params: { world: world.slug, id: w.id } }">{{ w.name }}</RouterLink></template>
          </span>
          <span v-if="node.here.length" class="small here">
            <span class="muted">here now: </span>
            <template v-for="(w, i) in node.here" :key="w.id"><span v-if="i" class="muted">, </span><span class="kname" :class="`k-${w.kind}`">{{ w.name }}</span></template>
          </span>
        </li>
      </ul>
      <p class="muted small">Places nest by “inside” / “contains”. Pick a chapter above to see who is recorded there in it.</p>
    </section>
  </template>
</template>
