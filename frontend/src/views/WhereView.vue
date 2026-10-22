<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { clearPresence, setPresence, whereGrid } from "../storytime";
import { useSession } from "../stores/session";
import type { EntityRef, WhereCell, WhereGrid } from "../types";
import { useCards } from "../world/cards";
import NotFoundView from "./NotFoundView.vue";

// Where everyone is: characters down, chapters across. A cell shows the place recorded with "is at", else the place
// named in the same paragraph (fainter, with a "?"), else a dot when the character is in the chapter at all.
const route = useRoute();
const session = useSession();
const cards = useCards();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const project = ref("");
const grid = ref<WhereGrid | null>(null);
const error = ref("");

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    grid.value = await whereGrid(worldSlug.value, project.value || undefined);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch([worldSlug, project], load, { immediate: true });
watch(worldSlug, (w) => void cards.load(w), { immediate: true });

const places = computed(() => cards.names.filter((n) => n.kind === "place"));
const projectsShown = computed(() => {
  const out: { name: string; span: number }[] = [];
  for (const c of grid.value?.chapters ?? []) {
    const last = out[out.length - 1];
    if (last?.name === c.project_name) last.span++;
    else out.push({ name: c.project_name, span: 1 });
  }
  return out;
});

// recording a place from a cell
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
const cellTitle = (c: WhereCell | undefined) =>
  !c
    ? "Not in this chapter"
    : c.recorded
      ? `Is at ${c.recorded.name}${c.note ? ` (${c.note})` : ""}`
      : c.derived
        ? `Probably at ${c.derived.name}: named in the same paragraph`
        : "In this chapter; where isn't known";
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
          means the character is in the chapter but where isn't known. Click a cell to record where they are.
        </p>
      </div>
      <div class="actions">
        <label for="where-project" class="visually-hidden">Project</label>
        <select id="where-project" v-model="project" class="filter">
          <option value="">The whole story</option>
          <option v-for="p in world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-if="grid && grid.chapters.length && grid.rows.length" class="card table-card">
      <table class="where-grid" data-testid="where-grid">
        <thead>
          <tr v-if="projectsShown.length > 1">
            <th />
            <th v-for="p in projectsShown" :key="p.name" :colspan="p.span" class="project-head">{{ p.name }}</th>
          </tr>
          <tr>
            <th class="corner" />
            <th v-for="(c, i) in grid.chapters" :key="c.id" class="chapter-head" :title="c.title">
              <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: c.id } }">
                <span class="num-label">{{ i + 1 }}</span> <span class="title">{{ c.title }}</span>
              </RouterLink>
            </th>
          </tr>
          <tr v-if="Object.keys(grid.events).length" class="events-row">
            <th class="muted small">Events</th>
            <td v-for="c in grid.chapters" :key="c.id" class="k-event">
              <RouterLink v-for="e in grid.events[c.id] ?? []" :key="e.id" class="kname small" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
            </td>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in grid.rows" :key="r.entity.id" :data-testid="`where-${r.entity.name}`">
            <th class="k-character">
              <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: r.entity.id } }">{{ r.entity.name }}</RouterLink>
            </th>
            <td
              v-for="c in grid.chapters"
              :key="c.id"
              class="cell"
              :class="{ recorded: r.cells[c.id]?.recorded, derived: !r.cells[c.id]?.recorded && r.cells[c.id]?.derived }"
              :title="cellTitle(r.cells[c.id])"
              :data-chapter="c.title"
            >
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
            </td>
          </tr>
        </tbody>
      </table>
    </section>
    <p v-else-if="grid" class="empty">
      {{ grid.chapters.length ? "No characters appear in these chapters yet." : "No chapters yet. Write some, and the people in them show up here." }}
    </p>
  </template>
</template>
