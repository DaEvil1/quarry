<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { addHarvestNote, getSalvage, reinstateChapter, type SalvageEntry } from "../manuscript";
import { useSession } from "../stores/session";
import NotFoundView from "./NotFoundView.vue";

// Retired chapters and closed experiments: what left the book, with notes on what was alive in each.
const route = useRoute();
const session = useSession();
const world = computed(() => session.world(String(route.params.world)));
const project = computed(() => (world.value ? session.project(world.value.slug, String(route.params.project)) : undefined));
const q = ref("");
const entries = ref<SalvageEntry[]>([]);
const error = ref("");
const noting = ref<string | null>(null);
const note = ref("");
let timer: ReturnType<typeof setTimeout> | undefined;

const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

async function load() {
  if (!world.value || !project.value) return;
  error.value = "";
  try {
    entries.value = await getSalvage(world.value.slug, project.value.slug, q.value.trim());
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(project, load, { immediate: true });
watch(q, () => {
  clearTimeout(timer);
  timer = setTimeout(load, 250);
});

async function saveNote(id: string) {
  if (!world.value || !note.value.trim()) return;
  await addHarvestNote(world.value.slug, id, note.value.trim());
  noting.value = null;
  note.value = "";
  await load();
}

async function reinstate(id: string) {
  if (!world.value) return;
  await reinstateChapter(world.value.slug, id);
  await load();
}
</script>

<template>
  <NotFoundView v-if="!world || !project" what="project" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'project', params: { world: world.slug, project: project.slug } }">{{ project.name }}</RouterLink>
        </div>
        <h1>Salvage</h1>
        <p class="muted">Chapters that left the book. Nothing here is lost; anything can go back.</p>
      </div>
    </div>

    <div class="toolbar">
      <label for="salvage-search" class="visually-hidden">Search</label>
      <input id="salvage-search" v-model="q" type="search" class="filter search" placeholder="Search titles, text and notes" />
    </div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-for="e in entries" :key="e.id" class="card" data-testid="salvage-entry">
      <div class="card-head">
        <h2><RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: e.id } }">{{ e.title }}</RouterLink></h2>
        <span class="muted small">
          {{ e.words.toLocaleString() }} words<template v-if="e.retired_at"> · retired {{ fmt.format(new Date(e.retired_at)) }}</template>
        </span>
      </div>
      <p v-if="e.match" class="snippet muted">{{ e.match.before }}<mark>{{ e.match.match }}</mark>{{ e.match.after }}</p>
      <ul v-if="e.harvest_notes.length" class="harvest">
        <li v-for="n in e.harvest_notes" :key="n.id">{{ n.body }}</li>
      </ul>
      <form v-if="noting === e.id" class="actions" @submit.prevent="saveNote(e.id)">
        <label :for="`note-${e.id}`" class="visually-hidden">Harvest note</label>
        <input :id="`note-${e.id}`" v-model="note" class="filter grow" type="text" maxlength="5000" placeholder="What was alive in it?" />
        <button class="btn btn-sm btn-primary" type="submit">Add</button>
        <button class="btn btn-sm" type="button" @click="noting = null">Cancel</button>
      </form>
      <div v-else class="actions">
        <button type="button" class="btn btn-sm" @click="(noting = e.id), (note = '')">Add a harvest note</button>
        <button type="button" class="btn btn-sm" @click="reinstate(e.id)">Put back in the book</button>
      </div>
    </section>
    <p v-if="!entries.length && !error" class="empty">{{ q ? "Nothing matches." : "Nothing retired yet." }}</p>
  </template>
</template>
