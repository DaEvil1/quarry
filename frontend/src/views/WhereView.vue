<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import EntityPicker from "../components/EntityPicker.vue";
import { clearPresence, setPresence, whereGrid } from "../storytime";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type EntityRef, type WhereCell, type WhereGrid, type WhereRow } from "../types";
import { useCards } from "../world/cards";
import { rowSteps, shareFilter, type Share } from "../world/where";
import NotFoundView from "./NotFoundView.vue";

// Where everyone is: entries down, chapters across (docs/SPEC.md §12.3). Characters by default, as before: a cell
// shows the place recorded with "is at", else the place named in the same paragraph (fainter, with a "?"), else a dot
// when they are in the chapter; clicking records where they are. Any kind can be added as rows, or one entry at a
// time: places show who is recorded there, everything else is shaded by how often the chapter names it. Ticking rows
// asks "do these share a chapter?". The choice is kept in the address, and the last one used per world on the device.
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const grid = ref<WhereGrid | null>(null);
const error = ref("");

// ---- the choice, in the address ----
const KEYS = ["kinds", "add", "hide", "project", "tick", "share"] as const;
const list = (key: string) => {
  const v = route.query[key];
  return typeof v === "string" && v ? v.split(",") : [];
};
const kinds = computed(() => (typeof route.query.kinds === "string" ? list("kinds") : ["character"]));
const added = computed(() => list("add"));
const hidden = computed(() => new Set(list("hide")));
const ticked = computed(() => new Set(list("tick")));
const project = computed(() => (typeof route.query.project === "string" ? route.query.project : ""));
const share = computed<Share>(() => (route.query.share === "any" || route.query.share === "every" ? route.query.share : "all"));
const memory = (w: string) => `quarry.where.${w}`;
function setQuery(changes: Record<string, string | string[] | undefined>) {
  const next: Record<string, string> = {};
  for (const [k, v] of Object.entries({ ...route.query, ...changes })) {
    if (v === undefined) continue;
    next[k] = Array.isArray(v) ? v.join(",") : String(v);
  }
  // remembered per world on this device
  try {
    localStorage.setItem(memory(worldSlug.value), JSON.stringify(next));
  } catch {
    /* storage unavailable */
  }
  void router.replace({ query: next });
}
// opening the page without a choice in the address: the last one used here
watch(
  worldSlug,
  (w) => {
    if (KEYS.some((k) => k in route.query)) return;
    try {
      const kept = JSON.parse(localStorage.getItem(memory(w)) ?? "null") as Record<string, string> | null;
      if (kept && Object.keys(kept).length) void router.replace({ query: kept });
    } catch {
      /* nothing kept */
    }
  },
  { immediate: true },
);

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    grid.value = await whereGrid(worldSlug.value, { project: project.value || undefined, kinds: kinds.value, entities: added.value });
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch([worldSlug, () => project.value, () => kinds.value.join(","), () => added.value.join(",")], load, { immediate: true });
watch(worldSlug, (w) => void cards.load(w), { immediate: true });

function toggleKind(k: string) {
  const next = kinds.value.includes(k) ? kinds.value.filter((x) => x !== k) : [...kinds.value, k];
  setQuery({ kinds: next.join(",") });
}
function addRow(e: EntityRef) {
  setQuery({ add: [...new Set([...added.value, e.id])], hide: list("hide").filter((x) => x !== e.id) });
}
function hideRow(id: string) {
  setQuery({ hide: [...hidden.value, id], tick: list("tick").filter((x) => x !== id) });
}
const showRow = (id: string) => setQuery({ hide: list("hide").filter((x) => x !== id) });
function tick(id: string, on: boolean) {
  setQuery({ tick: on ? [...ticked.value, id] : list("tick").filter((x) => x !== id) });
}

const rows = computed(() => (grid.value?.rows ?? []).filter((r) => !hidden.value.has(r.entity.id)));
const hiddenRows = computed(() => (grid.value?.rows ?? []).filter((r) => hidden.value.has(r.entity.id)));
const found = computed(() => (grid.value ? shareFilter(grid.value, rows.value, new Set([...ticked.value].filter((id) => rows.value.some((r) => r.entity.id === id))), share.value) : { chapters: [], line: "" }));
// told order (the book's, by default) or happened order, once any chapter has a time (docs/SPEC.md §13.1.4): the
// clock first, then the chapters outside time, in book order
const order = computed(() => (route.query.order === "happened" ? "happened" : "told"));
const timed = computed(() => (grid.value?.chapters ?? []).some((c) => c.time_at != null || c.outside_time || c.told_as));
const chapters = computed(() => {
  const keep = new Set(found.value.chapters);
  const list = (grid.value?.chapters ?? []).map((c, i) => ({ ...c, n: i + 1 })).filter((c) => keep.has(c.id));
  if (order.value !== "happened") return list;
  const onClock = list.filter((c) => c.clock != null).sort((a, b) => a.clock! - b.clock!);
  return [...onClock, ...list.filter((c) => c.clock == null)];
});
const headWhen = (c: { set_text?: string; early?: boolean; time_at?: number | null }) => (c.early ? "before the story" : (c.set_text ?? ""));
const projectsShown = computed(() => {
  const out: { name: string; span: number }[] = [];
  for (const c of chapters.value) {
    const last = out[out.length - 1];
    if (last?.name === c.project_name) last.span++;
    else out.push({ name: c.project_name, span: 1 });
  }
  return out;
});
const steps = computed(() => new Map(rows.value.map((r) => [r.entity.id, rowSteps(r)])));
const places = computed(() => cards.names.filter((n) => n.kind === "place"));
const KINDS = ENTITY_KINDS;

// recording a place from a character's cell
const editing = ref<string | null>(null);
const key = (entity: EntityRef, chapterId: string) => `${entity.id}|${chapterId}`;
async function record(entity: EntityRef, chapterId: string, placeId: string) {
  editing.value = null;
  error.value = "";
  try {
    if (placeId) await setPresence(worldSlug.value, chapterId, entity.id, placeId);
    else await clearPresence(worldSlug.value, chapterId, entity.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
const named = (c: WhereCell | undefined) => (c?.count ? `named ${c.count === 1 ? "once" : `${c.count} times`}` : "not named");
const cellTitle = (r: WhereRow, c: WhereCell | undefined) => {
  if (r.entity.kind === "character") {
    return !c
      ? "Not in this chapter"
      : c.recorded
        ? `Is at ${c.recorded.name}${c.note ? ` (${c.note})` : ""}`
        : c.derived
          ? `Probably at ${c.derived.name}: named in the same paragraph`
          : "In this chapter; where isn't known";
  }
  if (r.entity.kind === "place" && c?.people.length) return `${named(c)} · here: ${c.people.map((p) => p.name).join(", ")}`;
  return named(c);
};
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Where everyone is</h1>
        <p class="muted">
          Recorded places are solid; a place named in the same paragraph is shown fainter with a question mark; a dot
          means the character is in the chapter but where isn't known. Click a cell to record where they are. Other
          entries are shaded by how often the chapter names them.
        </p>
      </div>
      <div class="actions">
        <label for="where-project" class="visually-hidden">Project</label>
        <select id="where-project" class="filter" :value="project" @change="setQuery({ project: ($event.target as HTMLSelectElement).value || undefined })">
          <option value="">The whole story</option>
          <option v-for="p in world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
      </div>
    </div>

    <div class="toolbar where-tools">
      <span v-for="k in KINDS" :key="k.value" class="chip static" :class="`k-${k.value}`" :data-testid="`where-kind-${k.value}`">
        <label><input type="checkbox" :checked="kinds.includes(k.value)" @change="toggleKind(k.value)" /> <span class="kname">{{ k.plural }}</span></label>
      </span>
      <div class="where-add" data-testid="where-add">
        <EntityPicker :entities="cards.names" :exclude="rows.map((r) => r.entity.id)" placeholder="Add…" @pick="addRow" @cancel="() => {}" />
      </div>
      <label v-if="timed" class="small muted">Order
        <select class="filter" :value="order" data-testid="where-order" @change="setQuery({ order: ($event.target as HTMLSelectElement).value === 'happened' ? 'happened' : undefined })">
          <option value="told">told</option>
          <option value="happened">happened</option>
        </select>
      </label>
      <label class="small muted">Chapters
        <select class="filter" :value="share" data-testid="where-share" @change="setQuery({ share: ($event.target as HTMLSelectElement).value === 'all' ? undefined : ($event.target as HTMLSelectElement).value })">
          <option value="all">all</option>
          <option value="any">naming any of them</option>
          <option value="every">naming all of them</option>
        </select>
      </label>
    </div>
    <p v-if="found.line" class="small share-line" data-testid="share-line">{{ found.line }}</p>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-if="grid && grid.chapters.length && rows.length" class="card table-card">
      <table class="where-grid" data-testid="where-grid">
        <thead>
          <tr v-if="projectsShown.length > 1 && order === 'told'">
            <th />
            <th v-for="p in projectsShown" :key="p.name" :colspan="p.span" class="project-head">{{ p.name }}</th>
          </tr>
          <tr>
            <th class="corner" />
            <th v-for="c in chapters" :key="c.id" class="chapter-head" :title="c.title" :data-n="c.n">
              <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: c.id } }">
                <span class="num-label">{{ c.n }}</span> <span class="title">{{ c.title }}</span>
              </RouterLink>
              <span v-if="c.pov" class="pov-head small k-character" :title="`Told from ${c.pov.name}'s point of view`">{{ c.pov.name }}</span>
              <span v-if="timed && (headWhen(c) || c.told_as)" class="small muted head-when" data-testid="head-when">{{ [c.told_as, headWhen(c)].filter(Boolean).join(" · ") }}</span>
            </th>
          </tr>
          <tr v-if="Object.keys(grid.events).length" class="events-row">
            <th class="muted small">Events</th>
            <td v-for="c in chapters" :key="c.id" class="k-event">
              <RouterLink v-for="e in grid.events[c.id] ?? []" :key="e.id" class="kname small" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
            </td>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.entity.id" :data-testid="`where-${r.entity.name}`" :class="`k-${r.entity.kind}`">
            <th :class="`k-${r.entity.kind}`">
              <span class="row-head">
                <input type="checkbox" :checked="ticked.has(r.entity.id)" :aria-label="`Tick ${r.entity.name}`" data-testid="where-tick" @change="tick(r.entity.id, ($event.target as HTMLInputElement).checked)" />
                <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: r.entity.id } }">{{ r.entity.name }}</RouterLink>
                <button type="button" class="icon-btn small" :aria-label="`Hide ${r.entity.name}`" @click="hideRow(r.entity.id)">×</button>
              </span>
            </th>
            <td
              v-for="c in chapters"
              :key="c.id"
              class="cell"
              :class="[r.entity.kind === 'character' ? { recorded: r.cells[c.id]?.recorded, derived: !r.cells[c.id]?.recorded && r.cells[c.id]?.derived } : `s${steps.get(r.entity.id)?.get(c.id) ?? 0}`]"
              :title="cellTitle(r, r.cells[c.id])"
              :data-chapter="c.title"
              :data-count="r.cells[c.id]?.count ?? 0"
            >
              <template v-if="r.entity.kind === 'character'">
                <select
                  v-if="editing === key(r.entity, c.id)"
                  class="filter"
                  aria-label="Is at"
                  :value="r.cells[c.id]?.recorded?.id ?? ''"
                  @change="record(r.entity, c.id, ($event.target as HTMLSelectElement).value)"
                  @blur="editing = null"
                  @keydown.esc="editing = null"
                >
                  <option value="">— not recorded —</option>
                  <option v-for="p in places" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <button v-else type="button" class="cell-btn" @click="editing = key(r.entity, c.id)">
                  <span v-if="r.cells[c.id]?.recorded" class="k-place kname">{{ r.cells[c.id]!.recorded!.name }}</span>
                  <span v-else-if="r.cells[c.id]?.derived" class="k-place kname">{{ r.cells[c.id]!.derived!.name }}?</span>
                  <span v-else-if="r.cells[c.id]" class="dot" aria-label="present">•</span>
                  <span v-else class="visually-hidden">not here</span>
                </button>
              </template>
              <span v-else class="shade">
                <span v-if="r.entity.kind === 'place' && r.cells[c.id]?.people.length" class="people" data-testid="place-people">{{ r.cells[c.id]!.people.length }}</span>
                <span v-else-if="r.cells[c.id]?.count" class="visually-hidden">named {{ r.cells[c.id]!.count }}</span>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
    <p v-else-if="grid" class="empty">
      {{ grid.chapters.length ? (rows.length || hiddenRows.length ? "No chapter matches." : "Nothing chosen appears in these chapters yet.") : "No chapters yet. Write some, and the people in them show up here." }}
    </p>
    <p v-if="hiddenRows.length" class="small muted hidden-rows" data-testid="hidden-rows">
      Hidden:
      <template v-for="(r, i) in hiddenRows" :key="r.entity.id"><span v-if="i">, </span><button type="button" class="linkish" @click="showRow(r.entity.id)">{{ r.entity.name }}</button></template>
    </p>
  </template>
</template>
