<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { del, get, patch, post } from "../api";
import ProjectFilter from "../components/ProjectFilter.vue";
import { useSession } from "../stores/session";
import { WORLD_ONLY, localToday, type Decision } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const session = useSession();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const base = computed(() => `/api/worlds/${encodeURIComponent(worldSlug.value)}/decisions`);
const project = ref("");
const decisions = ref<Decision[]>([]);
const error = ref("");

const text = ref("");
const day = ref(localToday());
const newProject = ref("");

const editing = ref<string | null>(null);
const editText = ref("");

const fmt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const groups = computed(() => {
  const out: { day: string; label: string; items: Decision[] }[] = [];
  for (const d of decisions.value) {
    const last = out[out.length - 1];
    if (last?.day === d.decided_on) last.items.push(d);
    else out.push({ day: d.decided_on, label: fmt.format(new Date(`${d.decided_on}T12:00:00`)), items: [d] });
  }
  return out;
});
const projectName = (slug: string | null) => world.value?.projects.find((p) => p.slug === slug)?.name ?? slug;

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    const q = project.value ? `?project=${encodeURIComponent(project.value)}` : "";
    decisions.value = await get<Decision[]>(`${base.value}${q}`);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch([worldSlug, project], load, { immediate: true });
watch(project, (p) => (newProject.value = p === WORLD_ONLY ? "" : p));

async function add() {
  error.value = "";
  try {
    await post(base.value, { text: text.value, decided_on: day.value, project: newProject.value || null });
    text.value = "";
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function saveEdit(d: Decision) {
  error.value = "";
  try {
    await patch(`${base.value}/${d.id}`, { text: editText.value });
    editing.value = null;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function remove(d: Decision) {
  if (!confirm(`Remove this decision?\n\n${d.text}`)) return;
  await del(`${base.value}/${d.id}`);
  await load();
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Decisions</h1>
        <p class="muted">Dated one-line verdicts. The reasoning stays wherever you wrote it.</p>
      </div>
      <ProjectFilter v-model="project" :world="world" />
    </div>

    <form class="card form wide" @submit.prevent="add">
      <div class="field">
        <label for="decision-text">New decision</label>
        <input id="decision-text" v-model="text" type="text" maxlength="1000" required />
      </div>
      <div class="actions">
        <label for="decision-day" class="visually-hidden">Date</label>
        <input id="decision-day" v-model="day" type="date" class="filter" required />
        <label for="decision-project" class="visually-hidden">Project</label>
        <select id="decision-project" v-model="newProject" class="filter">
          <option value="">Whole world</option>
          <option v-for="p in world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
        <button class="btn btn-primary" type="submit">Log it</button>
      </div>
    </form>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-for="g in groups" :key="g.day" class="card">
      <h2 class="small muted">{{ g.label }}</h2>
      <ul class="rows" data-testid="decision-list">
        <li v-for="d in g.items" :key="d.id">
          <form v-if="editing === d.id" class="actions grow" @submit.prevent="saveEdit(d)">
            <label :for="`edit-${d.id}`" class="visually-hidden">Decision</label>
            <input :id="`edit-${d.id}`" v-model="editText" class="grow filter" type="text" maxlength="1000" required />
            <button class="btn btn-sm btn-primary" type="submit">Save</button>
            <button class="btn btn-sm" type="button" @click="editing = null">Cancel</button>
          </form>
          <template v-else>
            <span class="grow">{{ d.text }}</span>
            <span v-if="d.project" class="pill">{{ projectName(d.project) }}</span>
            <span v-if="d.item_id" class="pill accent" title="Logged while closing an item">from triage</span>
            <button type="button" class="icon-btn small" @click="(editing = d.id), (editText = d.text)">Edit</button>
            <button type="button" class="icon-btn small" @click="remove(d)">Remove</button>
          </template>
        </li>
      </ul>
    </section>
    <p v-if="!decisions.length && !error" class="empty">No decisions logged yet.</p>
  </template>
</template>
