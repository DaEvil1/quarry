<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { ApiError, del, get, patch, post } from "../api";
import ProjectFilter from "../components/ProjectFilter.vue";
import { useSession } from "../stores/session";
import { WORLD_ONLY, localToday, type JournalEntry } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const session = useSession();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const base = computed(() => `/api/worlds/${encodeURIComponent(worldSlug.value)}/journal`);
const project = ref("");
const entries = ref<JournalEntry[]>([]);
const error = ref("");

// the entry being written or edited; id null = a new one
const draft = ref<{ id: string | null; version: number; date: string; title: string; body: string; project: string } | null>(null);
const box = ref<HTMLTextAreaElement | null>(null);

const fmt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const day = (iso: string) => fmt.format(new Date(`${iso}T12:00:00`));
const projectName = (slug: string | null) => world.value?.projects.find((p) => p.slug === slug)?.name ?? slug;

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    const q = project.value ? `?project=${encodeURIComponent(project.value)}` : "";
    entries.value = await get<JournalEntry[]>(`${base.value}${q}`);
    if (route.hash) {
      await nextTick();
      document.querySelector(route.hash)?.scrollIntoView({ block: "start" });
    }
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch([worldSlug, project], load, { immediate: true });

async function write(entry?: JournalEntry) {
  draft.value = entry
    ? { id: entry.id, version: entry.version, date: entry.entry_date, title: entry.title ?? "", body: entry.body, project: entry.project ?? "" }
    : { id: null, version: 0, date: localToday(), title: "", body: "", project: project.value === WORLD_ONLY ? "" : project.value };
  await nextTick();
  box.value?.focus();
}

async function save() {
  const d = draft.value;
  if (!d) return;
  error.value = "";
  const payload = { entry_date: d.date, title: d.title || null, body: d.body, project: d.project || null };
  try {
    if (d.id) await patch(`${base.value}/${d.id}`, { base_version: d.version, ...payload });
    else await post(base.value, payload);
    draft.value = null;
    await load();
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 409 ? `${e.message} Copy your text before reloading.` : (e as Error).message;
  }
}

async function remove(entry: JournalEntry) {
  if (!confirm("Remove this journal entry?")) return;
  await del(`${base.value}/${entry.id}`);
  await load();
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Journal</h1>
        <p class="muted">Thinking on paper. Dated, never wrong, only older.</p>
      </div>
      <div class="actions">
        <ProjectFilter v-model="project" :world="world" />
        <button v-if="!draft" type="button" class="btn btn-primary btn-sm" @click="write()">New entry</button>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <form v-if="draft" class="card form wide" @submit.prevent="save">
      <div class="actions">
        <label for="j-date" class="visually-hidden">Date</label>
        <input id="j-date" v-model="draft.date" type="date" class="filter" required />
        <label for="j-project" class="visually-hidden">Project</label>
        <select id="j-project" v-model="draft.project" class="filter">
          <option value="">Whole world</option>
          <option v-for="p in world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
      </div>
      <div class="field">
        <label for="j-title">Title <span class="muted">(optional)</span></label>
        <input id="j-title" v-model="draft.title" type="text" maxlength="300" />
      </div>
      <div class="field">
        <label for="j-body" class="visually-hidden">Entry</label>
        <textarea id="j-body" ref="box" v-model="draft.body" class="capture-box" rows="14" placeholder="What does the story want right now?" />
      </div>
      <div class="actions">
        <button class="btn btn-primary" type="submit">Save</button>
        <button class="btn" type="button" @click="draft = null">Cancel</button>
      </div>
    </form>

    <article v-for="e in entries" :id="`entry-${e.id}`" :key="e.id" class="card journal-entry" data-testid="journal-entry">
      <div class="card-head">
        <div>
          <div class="muted small">{{ day(e.entry_date) }}<template v-if="e.project"> · {{ projectName(e.project) }}</template></div>
          <h2 v-if="e.title">{{ e.title }}</h2>
        </div>
        <div class="actions">
          <button type="button" class="icon-btn small" @click="write(e)">Edit</button>
          <button type="button" class="icon-btn small" @click="remove(e)">Remove</button>
        </div>
      </div>
      <p class="prose item-text">{{ e.body }}</p>
    </article>
    <p v-if="!entries.length && !draft && !error" class="empty">No entries yet.</p>
  </template>
</template>
