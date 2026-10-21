<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get, patch } from "../api";
import { age, listItems } from "../items";
import { createChapter, getManuscript, reorderChapters, type ChapterInfo, type Manuscript } from "../manuscript";
import { useSession } from "../stores/session";
import { PROJECT_KINDS, firstLine, kindLabel, type Item, type Project, type ProjectKind, type World } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();

const world = computed(() => session.world(String(route.params.world)));
const project = computed(() =>
  world.value ? session.project(world.value.slug, String(route.params.project)) : undefined,
);

const manuscript = ref<Manuscript | null>(null);
const openItems = ref<Item[]>([]);
const error = ref("");

async function load() {
  const w = world.value;
  const p = project.value;
  if (!w || !p) return;
  error.value = "";
  try {
    [manuscript.value, openItems.value] = await Promise.all([
      getManuscript(w.slug, p.slug),
      listItems(w.slug, { project: p.slug, limit: 20 }),
    ]);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(project, load, { immediate: true });

// experiments listed under the chapter they would replace
const experimentsOf = (id: string) => manuscript.value?.experiments.filter((x) => x.replaces_id === id) ?? [];
const orphanExperiments = computed(() => {
  const ids = new Set(manuscript.value?.chapters.map((c) => c.id));
  return manuscript.value?.experiments.filter((x) => !x.replaces_id || !ids.has(x.replaces_id)) ?? [];
});

// ---- new chapter ----
const newTitle = ref("");
async function addChapter() {
  const w = world.value;
  const p = project.value;
  if (!w || !p || !newTitle.value.trim()) return;
  try {
    const ch = await createChapter(w.slug, p.slug, newTitle.value);
    newTitle.value = "";
    await router.push({ name: "chapter", params: { world: w.slug, id: ch.id } });
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// ---- order: drag a row, or use the arrows ----
const dragging = ref<string | null>(null);
async function saveOrder(chapters: ChapterInfo[]) {
  const w = world.value;
  const p = project.value;
  if (!w || !p || !manuscript.value) return;
  manuscript.value.chapters = chapters.map((c, i) => ({ ...c, position: i }));
  try {
    await reorderChapters(w.slug, p.slug, chapters.map((c) => c.id));
  } catch (e) {
    error.value = (e as Error).message;
    await load();
  }
}
function move(index: number, by: -1 | 1) {
  const list = [...(manuscript.value?.chapters ?? [])];
  const [c] = list.splice(index, 1);
  list.splice(index + by, 0, c);
  void saveOrder(list);
}
function drop(targetId: string) {
  const list = [...(manuscript.value?.chapters ?? [])];
  const from = list.findIndex((c) => c.id === dragging.value);
  const to = list.findIndex((c) => c.id === targetId);
  dragging.value = null;
  if (from < 0 || to < 0 || from === to) return;
  const [c] = list.splice(from, 1);
  list.splice(to, 0, c);
  void saveOrder(list);
}

// ---- rename ----
const editing = ref(false);
const name = ref("");
const slug = ref("");
const kind = ref<ProjectKind>("novel");
watch(project, () => (editing.value = false));

function startEdit() {
  if (!project.value) return;
  name.value = project.value.name;
  slug.value = project.value.slug;
  kind.value = project.value.kind;
  error.value = "";
  editing.value = true;
}

async function save() {
  const w = world.value;
  const p = project.value;
  if (!w || !p) return;
  error.value = "";
  try {
    const updated = await patch<Project>(`/api/worlds/${w.slug}/projects/${p.slug}`, {
      name: name.value,
      slug: slug.value.trim(),
      kind: kind.value,
    });
    session.putWorld(await get<World>(`/api/worlds/${w.slug}`));
    editing.value = false;
    if (updated.slug !== p.slug) {
      await router.replace({ name: "project", params: { world: w.slug, project: updated.slug } });
    }
  } catch (e) {
    error.value = (e as Error).message;
  }
}
</script>

<template>
  <NotFoundView v-if="!world || !project" what="project" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'world', params: { world: world.slug } }">{{ world.name }}</RouterLink>
          · {{ kindLabel(project.kind) }}
        </div>
        <h1>{{ project.name }}</h1>
        <p v-if="manuscript" class="muted" data-testid="manuscript-summary">
          {{ manuscript.chapters.length }} chapters · {{ manuscript.words.toLocaleString() }} words
        </p>
      </div>
      <div class="actions">
        <RouterLink class="btn btn-sm" :to="{ name: 'salvage', params: { world: world.slug, project: project.slug } }">
          Salvage<template v-if="manuscript?.retired"> ({{ manuscript.retired }})</template>
        </RouterLink>
        <button v-if="!editing" type="button" class="btn btn-sm" @click="startEdit">Edit</button>
      </div>
    </div>

    <form v-if="editing" class="card form" @submit.prevent="save">
      <div class="field">
        <label for="p-name">Name</label>
        <input id="p-name" v-model="name" type="text" maxlength="200" required />
      </div>
      <div class="field">
        <label for="p-kind">Kind</label>
        <select id="p-kind" v-model="kind">
          <option v-for="k in PROJECT_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
      </div>
      <div class="field">
        <label for="p-slug">Address</label>
        <input id="p-slug" v-model="slug" type="text" maxlength="60" spellcheck="false" required />
        <div class="hint">Shown in links as /w/{{ world.slug }}/p/{{ slug || "…" }}.</div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" type="submit">Save</button>
        <button class="btn" type="button" @click="editing = false">Cancel</button>
      </div>
    </form>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section class="card">
      <div class="card-head"><h2>Manuscript</h2></div>
      <ol class="chapters" data-testid="chapters">
        <template v-for="(c, i) in manuscript?.chapters ?? []" :key="c.id">
          <li
            class="chapter-row"
            :class="{ dragging: dragging === c.id }"
            draggable="true"
            @dragstart="dragging = c.id"
            @dragend="dragging = null"
            @dragover.prevent
            @drop.prevent="drop(c.id)"
          >
            <span class="drag" aria-hidden="true">⋮⋮</span>
            <span class="muted small chapter-no">{{ i + 1 }}</span>
            <RouterLink class="grow" :to="{ name: 'chapter', params: { world: world.slug, id: c.id } }">{{ c.title }}</RouterLink>
            <span v-if="c.pov" class="pill">{{ c.pov.name }}</span>
            <span class="muted small chapter-words">{{ c.words.toLocaleString() }} w</span>
            <button type="button" class="icon-btn" :disabled="i === 0" :aria-label="`Move ${c.title} up`" @click="move(i, -1)">
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 10l5-5 5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
            </button>
            <button
              type="button"
              class="icon-btn"
              :disabled="i === (manuscript?.chapters.length ?? 0) - 1"
              :aria-label="`Move ${c.title} down`"
              @click="move(i, 1)"
            >
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
            </button>
          </li>
          <li v-for="x in experimentsOf(c.id)" :key="x.id" class="chapter-row experiment">
            <span class="pill accent">experiment</span>
            <RouterLink class="grow" :to="{ name: 'chapter', params: { world: world.slug, id: x.id } }">{{ x.title }}</RouterLink>
            <span class="muted small chapter-words">{{ x.words.toLocaleString() }} w</span>
          </li>
        </template>
        <li v-for="x in orphanExperiments" :key="x.id" class="chapter-row experiment">
          <span class="pill accent">experiment</span>
          <RouterLink class="grow" :to="{ name: 'chapter', params: { world: world.slug, id: x.id } }">{{ x.title }}</RouterLink>
        </li>
      </ol>
      <p v-if="manuscript && !manuscript.chapters.length" class="empty">No chapters yet.</p>
      <form class="actions new-chapter" @submit.prevent="addChapter">
        <label for="new-chapter" class="visually-hidden">New chapter title</label>
        <input id="new-chapter" v-model="newTitle" class="filter grow" type="text" maxlength="300" placeholder="New chapter title" />
        <button class="btn btn-primary btn-sm" type="submit" :disabled="!newTitle.trim()">Add chapter</button>
      </form>
    </section>

    <section v-if="manuscript?.pov_tally.length" class="card">
      <div class="card-head"><h2>Point of view</h2></div>
      <ul class="rows" data-testid="pov-tally">
        <li v-for="p in manuscript.pov_tally" :key="p.name">
          <span class="grow">{{ p.name }}</span>
          <span class="muted small">{{ p.chapters }} {{ p.chapters === 1 ? "chapter" : "chapters" }}</span>
        </li>
      </ul>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Open items</h2>
        <div class="actions">
          <RouterLink class="btn btn-sm" :to="{ name: 'triage', params: { world: world.slug }, query: { project: project.slug } }">
            Triage
          </RouterLink>
          <RouterLink :to="{ name: 'inbox', params: { world: world.slug }, query: { project: project.slug } }">Inbox</RouterLink>
        </div>
      </div>
      <ul v-if="openItems.length" class="rows">
        <li v-for="i in openItems" :key="i.id">
          <span class="pill" :class="`kind-${i.kind}`">{{ i.kind }}</span>
          <RouterLink class="grow" :to="{ name: 'item', params: { world: world.slug, id: i.id } }">{{ firstLine(i) }}</RouterLink>
          <span class="muted small">{{ age(i.created_at) }}</span>
        </li>
      </ul>
      <p v-else class="empty">Nothing open for this project.</p>
    </section>
  </template>
</template>
