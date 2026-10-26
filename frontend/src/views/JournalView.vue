<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { unreachable } from "../api";
import MentionText from "../components/MentionText.vue";
import ProjectFilter from "../components/ProjectFilter.vue";
import { createEntry, journalDay, listJournal } from "../journal";
import { localJournal, queueEntry } from "../offline";
import { useSession } from "../stores/session";
import { WORLD_ONLY, localToday, planChapterText, type JournalEntry, type Mention } from "../types";
import { useCards } from "../world/cards";
import { markers } from "../world/markers";
import StartChapter from "../components/StartChapter.vue";
import NotFoundView from "./NotFoundView.vue";

// The Journal (docs/SPEC.md §14.1.1, §14.3.2): the entries in date order, newest first, with their first lines and the
// names in them coloured; New entry makes one dated today and opens it in the editor. Loose ends lists every TK and
// "??" marker, oldest entry first. Both are read from the copy on this device when the server can't be reached.

const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const project = ref("");
const search = ref("");
const entries = ref<JournalEntry[]>([]);
const error = ref("");
const offline = ref(false);
const tab = ref<"entries" | "loose">(route.query.tab === "loose" ? "loose" : "entries");
watch(tab, (t) => void router.replace({ query: { ...route.query, tab: t === "loose" ? "loose" : undefined } }));
// All · Plans (docs/SPEC.md §18.1), kept in the address
const plansOnly = computed(() => route.query.plans === "1");
const setPlans = (on: boolean) => void router.replace({ query: { ...route.query, plans: on ? "1" : undefined } });
/** "plan · chapter 4, The Quay", "plan · 3 chapters", "plan · no chapter yet" */
function planTag(e: JournalEntry): string {
  const cs = e.chapters ?? [];
  return `plan · ${cs.length === 1 ? planChapterText(cs[0]!) : cs.length ? `${cs.length} chapters` : "no chapter yet"}`;
}

const projectName = (slug: string | null) => world.value?.projects.find((p) => p.slug === slug)?.name ?? slug;

async function load() {
  if (!world.value) return;
  error.value = "";
  void cards.load(worldSlug.value);
  try {
    entries.value = await listJournal(worldSlug.value, project.value);
    offline.value = false;
  } catch (e) {
    if (!unreachable(e)) {
      error.value = (e as Error).message;
      return;
    }
    offline.value = true;
    const all = await localJournal(worldSlug.value);
    entries.value = project.value === WORLD_ONLY ? all.filter((j) => !j.project) : project.value ? all.filter((j) => j.project === project.value) : all;
  }
}
watch([worldSlug, project], load, { immediate: true });

const shown = computed(() => {
  const q = search.value.trim().toLowerCase();
  const list = plansOnly.value ? entries.value.filter((e) => e.is_plan) : entries.value;
  return q ? list.filter((e) => `${e.title ?? ""}\n${e.body}`.toLowerCase().includes(q)) : list;
});

/** An entry's first lines, about 300 characters, ending on a word. */
function opening(body: string): string {
  const text = body.trim();
  if (text.length <= 300) return text;
  const cut = text.slice(0, 300);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), 200))}…`;
}
/** The names in an entry's first lines, found on the device the way the editor finds them. */
function namesIn(text: string): Mention[] {
  const m = cards.matcher();
  return m.scanSource(text, "journal", false).map((h) => ({ entity_id: h.entityId, entity_name: cards.byId.get(h.entityId)?.name ?? h.matched, entity_kind: cards.byId.get(h.entityId)?.kind, start: h.start, end: h.end, matched_text: h.matched, kind: h.kind === "ambiguous" ? "ambiguous" : "exact" }));
}

// ---- a new entry, dated today; made on the device when there is no connection ----
const making = ref(false);
async function newEntry() {
  if (making.value) return;
  making.value = true;
  error.value = "";
  const id = crypto.randomUUID();
  const forProject = project.value && project.value !== WORLD_ONLY ? project.value : null;
  try {
    await createEntry(worldSlug.value, { id, entry_date: localToday(), project: forProject });
  } catch (e) {
    if (!unreachable(e)) {
      error.value = (e as Error).message;
      making.value = false;
      return;
    }
    await queueEntry({ id, world: worldSlug.value, entry_date: localToday(), title: null, project: forProject });
  }
  making.value = false;
  await router.push({ name: "journal-entry", params: { world: worldSlug.value, id } });
}

// ---- loose ends: every TK and ?? marker, oldest entry first ----
const loose = computed(() =>
  [...entries.value]
    .reverse()
    .map((e) => ({ entry: e, marks: markers(e.body) }))
    .filter((x) => x.marks.length),
);
const markerCount = computed(() => loose.value.reduce((n, x) => n + x.marks.length, 0));
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
        <button type="button" class="btn btn-primary btn-sm" :disabled="making" data-testid="new-entry" @click="newEntry">New entry</button>
      </div>
    </div>

    <nav class="tabs" role="tablist">
      <button type="button" role="tab" class="tab" :aria-selected="tab === 'entries'" @click="tab = 'entries'">Entries</button>
      <button type="button" role="tab" class="tab" :aria-selected="tab === 'loose'" data-testid="loose-tab" @click="tab = 'loose'">
        Loose ends<span v-if="markerCount" class="badge dim">{{ markerCount }}</span>
      </button>
    </nav>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <div v-if="offline" class="notice offline small" role="status">Offline: the entries kept on this device.</div>

    <template v-if="tab === 'entries'">
      <div class="actions journal-filters">
        <input v-model="search" type="search" class="filter journal-search" placeholder="Search the Journal" aria-label="Search the Journal" />
        <span class="mode-switch" role="group" aria-label="Show" data-testid="plans-filter">
          <button type="button" :class="{ on: !plansOnly }" :aria-pressed="!plansOnly" @click="setPlans(false)">All</button>
          <button type="button" :class="{ on: plansOnly }" :aria-pressed="plansOnly" @click="setPlans(true)">Plans</button>
        </span>
      </div>
      <article v-for="e in shown" :id="`entry-${e.id}`" :key="e.id" class="card journal-entry" data-testid="journal-entry">
        <RouterLink class="journal-link" :to="{ name: 'journal-entry', params: { world: world.slug, id: e.id } }">
          <div class="muted small">
            {{ journalDay(e.entry_date) }}<template v-if="e.project"> · {{ projectName(e.project) }}</template>
            <span v-if="e.is_plan" class="plan-tag" data-testid="plan-tag"> · {{ planTag(e) }}</span>
            <span v-if="e.since" class="since-count" data-testid="since-count" title="Decisions and changes since this was written, touching what it names">{{ e.since }} since</span>
          </div>
          <h2>{{ e.title || "Untitled" }}</h2>
        </RouterLink>
        <p class="prose item-text">
          <MentionText :text="opening(e.body)" :mentions="namesIn(opening(e.body))" :world="world.slug" :source="{ table: 'journal', id: e.id }" />
        </p>
        <p v-if="plansOnly && e.is_plan && !(e.chapters ?? []).length" class="small"><StartChapter :world="world.slug" :entry="e" :projects="world.projects" @error="(m) => (error = m)" /></p>
      </article>
      <p v-if="!shown.length && !error" class="empty">{{ search ? "No entry says that." : "No entries yet." }}</p>
    </template>

    <section v-else data-testid="journal-loose">
      <p class="muted">{{ markerCount }} marker{{ markerCount === 1 ? "" : "s" }} in {{ loose.length }} entr{{ loose.length === 1 ? "y" : "ies" }}</p>
      <article v-for="x in loose" :key="x.entry.id" class="card journal-entry">
        <div class="muted small">{{ journalDay(x.entry.entry_date) }}</div>
        <h2>{{ x.entry.title || "Untitled" }}</h2>
        <ul class="plain-list">
          <li v-for="m in x.marks" :key="m.from">
            <RouterLink class="small" :to="{ name: 'journal-entry', params: { world: world.slug, id: x.entry.id }, query: { at: String(m.from) } }">{{ m.line }}</RouterLink>
          </li>
        </ul>
      </article>
      <p v-if="!loose.length" class="empty">No TK or ?? in the Journal.</p>
    </section>
  </template>
</template>
