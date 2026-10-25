<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { del, get, patch, post } from "../api";
import DecisionFollowups from "../components/DecisionFollowups.vue";
import EntityPicker from "../components/EntityPicker.vue";
import { followersText, listFollowups } from "../followups";
import ProjectFilter from "../components/ProjectFilter.vue";
import { useSession } from "../stores/session";
import { WORLD_ONLY, localToday, type Decision, type EntityRef } from "../types";
import { useCards } from "../world/cards";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const base = computed(() => `/api/worlds/${encodeURIComponent(worldSlug.value)}/decisions`);
const project = ref("");
// All · With open follow-ups (docs/SPEC.md §16.5), kept in the address
const openOnly = computed(() => route.query.followups === "open");
function setOpenOnly(on: boolean) {
  const { followups: _, ...rest } = route.query;
  void router.replace({ query: on ? { ...rest, followups: "open" } : rest });
}
const decisions = ref<Decision[]>([]);
// the decision just written here: it gets the follow-up step, as after a close (§16.3)
const justAdded = ref<string | null>(null);
const error = ref("");

const text = ref("");
const day = ref(localToday());
const newProject = ref("");

const editing = ref<string | null>(null);
const editText = ref("");

const fmt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const openCount = computed(() => decisions.value.reduce((n, d) => n + (d.followups?.todo ?? 0), 0));
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
    const params = new URLSearchParams();
    if (project.value) params.set("project", project.value);
    if (openOnly.value) params.set("followups", "open");
    const q = params.toString();
    decisions.value = await get<Decision[]>(`${base.value}${q ? `?${q}` : ""}`);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch([worldSlug, project, openOnly], load, { immediate: true });
watch(project, (p) => (newProject.value = p === WORLD_ONLY ? "" : p));

async function add() {
  error.value = "";
  try {
    const d = await post<Decision>(base.value, { text: text.value, decided_on: day.value, project: newProject.value || null });
    text.value = "";
    await load();
    justAdded.value = d.id;
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

// tagging a decision with the bible entries it settles something about
const tagging = ref<string | null>(null);
async function setTags(d: Decision, entities: EntityRef[]) {
  error.value = "";
  tagging.value = null;
  try {
    await patch(`${base.value}/${d.id}`, { entities: entities.map((e) => e.id) });
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function remove(d: Decision) {
  const followers = d.followups ? followersText(await listFollowups(worldSlug.value, d.id).catch(() => [])) : "";
  if (!confirm(`Remove this decision?\n\n${d.text}${followers ? `\n\n${followers}` : ""}`)) return;
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
      <div class="actions">
        <div class="tabs" role="tablist" aria-label="Follow-ups">
          <button type="button" role="tab" class="tab" :aria-selected="!openOnly" @click="setOpenOnly(false)">All</button>
          <button type="button" role="tab" class="tab" :aria-selected="openOnly" data-testid="filter-open" @click="setOpenOnly(true)">With open follow-ups</button>
        </div>
        <ProjectFilter v-model="project" :world="world" />
      </div>
    </div>
    <p v-if="openOnly && decisions.length" class="muted small" data-testid="open-summary">
      {{ decisions.length }} {{ decisions.length === 1 ? "decision" : "decisions" }} with {{ openCount }} open {{ openCount === 1 ? "follow-up" : "follow-ups" }}, oldest first
    </p>

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
        <li v-for="d in g.items" :id="`d-${d.id}`" :key="d.id" class="fu-line">
          <form v-if="editing === d.id" class="actions grow" @submit.prevent="saveEdit(d)">
            <label :for="`edit-${d.id}`" class="visually-hidden">Decision</label>
            <input :id="`edit-${d.id}`" v-model="editText" class="grow filter" type="text" maxlength="1000" required />
            <button class="btn btn-sm btn-primary" type="submit">Save</button>
            <button class="btn btn-sm" type="button" @click="editing = null">Cancel</button>
          </form>
          <template v-else>
            <span class="grow">{{ d.text }}</span>
            <span v-for="e in d.entities" :key="e.id" class="chip static tag" :class="`k-${e.kind}`">
              <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
              <button type="button" class="chip-x" :aria-label="`Untag ${e.name}`" @click="setTags(d, d.entities.filter((x) => x.id !== e.id))">×</button>
            </span>
            <EntityPicker
              v-if="tagging === d.id"
              :entities="cards.names"
              :exclude="d.entities.map((e) => e.id)"
              placeholder="Tag with…"
              autofocus
              @pick="(e) => setTags(d, [...d.entities, e])"
              @cancel="tagging = null"
            />
            <button v-else type="button" class="icon-btn small" @click="tagging = d.id">Tag</button>
            <span v-if="d.project" class="pill">{{ projectName(d.project) }}</span>
            <span v-if="d.item_id" class="pill accent" title="Logged while closing an item">from triage</span>
            <button type="button" class="icon-btn small" @click="(editing = d.id), (editText = d.text)">Edit</button>
            <button type="button" class="icon-btn small" @click="remove(d)">Remove</button>
            <DecisionFollowups :key="`${d.id}-${openOnly}`" :world="world.slug" :decision="d" :open="openOnly" :step="justAdded === d.id" @counts="(c) => (d.followups = c)" />
          </template>
        </li>
      </ul>
    </section>
    <p v-if="!decisions.length && !error" class="empty">{{ openOnly ? "No decision has a follow-up to do." : "No decisions logged yet." }}</p>
  </template>
</template>
