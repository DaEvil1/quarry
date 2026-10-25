<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get, patch, post, put } from "../api";
import FocusSwitch from "../components/FocusSwitch.vue";
import InlineText from "../components/InlineText.vue";
import { getFront, howLongAgo, lately, type Front, type FrontNote } from "../front";
import { journalDay, listJournal } from "../journal";
import { exportUrl } from "../manuscript";
import { localJournal } from "../offline";
import { useSession } from "../stores/session";
import { PROJECT_KINDS, kindLabel, type Project, type ProjectKind, type World } from "../types";
import { markers } from "../world/markers";
import NotFoundView from "./NotFoundView.vue";

// The world's front page (docs/SPEC.md §14.4): the place to get back in after weeks or years away. A premise, the
// latest note for next time, what has been happening lately, the latest decisions, the open questions, and the
// projects. Every section hides while it would be empty. Rename, the time unit and Delete are on World settings.

const route = useRoute();
const session = useSession();
const world = computed(() => session.world(String(route.params.world)));
const front = ref<Front | null>(null);
const error = ref("");
const unsure = ref(0);

async function load() {
  const w = world.value;
  if (!w) return;
  error.value = "";
  try {
    front.value = await getFront(w.slug);
  } catch (e) {
    front.value = null;
    error.value = (e as Error).message;
  }
  // the ?? markers in the Journal, counted on the device (docs/SPEC.md §14.3.2)
  const entries = await listJournal(w.slug).catch(() => localJournal(w.slug));
  if (world.value?.slug === w.slug) unsure.value = entries.reduce((n, j) => n + markers(j.body).filter((m) => m.kind === "??").length, 0);
}
watch(() => world.value?.slug, load, { immediate: true });

async function setPremise(v: string) {
  const w = world.value;
  if (!w) return;
  try {
    session.putWorld(await patch<World>(`/api/worlds/${w.slug}`, { premise: v }));
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// where you left off
const showAllNotes = ref(false);
const notes = computed(() => front.value?.notes ?? []);
const fmtAgo = (iso: string | null) => (iso ? howLongAgo(iso.slice(0, 10)) : "");
function noteWhere(n: FrontNote): string {
  if (n.source === "journal") return `the Journal, ${n.date ? journalDay(n.date) : ""}${n.title ? ` · ${n.title}` : ""}`;
  return `${n.position ? `chapter ${n.position}, ` : ""}${n.title ?? ""}`;
}
const continueTo = (n: FrontNote) => ({
  name: n.source === "journal" ? "journal-entry" : "chapter",
  params: { world: world.value!.slug, id: n.id },
  query: { at: String(n.cursor) },
});

// lately, grouped by day on this device
const days = computed(() => lately(front.value?.lately ?? []));
const projectName = (slug: string | null) => world.value?.projects.find((p) => p.slug === slug)?.name ?? slug ?? "";
const dayTitle = (d: string) => `${journalDay(d)} · ${howLongAgo(d)}`;
const plural = (n: number, one: string, many: string) => `${n.toLocaleString()} ${n === 1 ? one : many}`;

// projects: order, a new one
const adding = ref(false);
const newName = ref("");
const newKind = ref<ProjectKind>("novel");
const newError = ref("");
const busy = ref(false);
async function refresh(slug: string) {
  session.putWorld(await get<World>(`/api/worlds/${slug}`));
}
async function addProject() {
  if (!world.value) return;
  newError.value = "";
  busy.value = true;
  try {
    await post<Project>(`/api/worlds/${world.value.slug}/projects`, { name: newName.value, kind: newKind.value });
    await refresh(world.value.slug);
    newName.value = "";
    adding.value = false;
    void load();
  } catch (e) {
    newError.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function move(index: number, by: -1 | 1) {
  const w = world.value;
  if (!w) return;
  const ids = w.projects.map((p) => p.id);
  const [id] = ids.splice(index, 1);
  ids.splice(index + by, 0, id);
  await put(`/api/worlds/${w.slug}/project-order`, { ids });
  await refresh(w.slug);
}
const projectInfo = (slug: string) => front.value?.projects.find((p) => p.slug === slug);
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">World</div>
        <h1>{{ world.name }}</h1>
        <p class="premise" data-testid="premise">
          <InlineText :value="world.premise ?? ''" label="Premise" placeholder="Add a premise" :maxlength="300" @save="setPremise" />
        </p>
      </div>
      <div class="actions">
        <FocusSwitch :world="world" />
        <a class="btn btn-sm" :href="exportUrl(world.slug)" download data-testid="export">Export</a>
        <RouterLink class="btn btn-sm" :to="{ name: 'world-settings', params: { world: world.slug } }" data-testid="world-settings">World settings</RouterLink>
      </div>
    </div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-if="notes.length" class="card front-section" data-testid="left-off">
      <div class="card-head"><h2>Where you left off</h2></div>
      <template v-for="(n, i) in showAllNotes ? notes : notes.slice(0, 1)" :key="n.source + n.id">
        <p :class="i ? 'small' : ''">
          <template v-if="n.note">“{{ n.note }}” — </template>{{ noteWhere(n) }}<span class="muted"> · {{ fmtAgo(n.updated_at) }}</span>
          · <RouterLink :to="continueTo(n)" :data-testid="i ? undefined : 'continue'">Continue</RouterLink>
        </p>
      </template>
      <button v-if="notes.length > 1 && !showAllNotes" type="button" class="linkish small" @click="showAllNotes = true">{{ notes.length - 1 }} more</button>
    </section>

    <section v-if="days.length" class="card front-section" data-testid="lately">
      <div class="card-head"><h2>Lately</h2></div>
      <div v-for="d in days" :key="d.day" class="lately-day" data-testid="lately-day">
        <h3 class="small">{{ dayTitle(d.day) }}</h3>
        <p class="small">
          <template v-for="w in d.words" :key="w.project ?? '-'">
            <RouterLink v-if="w.project" :to="{ name: 'project', params: { world: world.slug, project: w.project } }">{{ plural(w.n, "word", "words") }} in {{ projectName(w.project) }}</RouterLink> ·
          </template>
          <template v-if="d.journal"><RouterLink :to="{ name: 'journal', params: { world: world.slug } }">{{ plural(d.journal, "journal entry", "journal entries") }}</RouterLink> · </template>
          <template v-if="d.entities.length">
            <template v-for="(e, k) in d.entities.slice(0, 3)" :key="e.id"><RouterLink class="kname" :class="`k-${e.kind}`" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>{{ k < Math.min(d.entities.length, 3) - 1 ? ", " : "" }}</template>
            <template v-if="d.entities.length > 3"> and {{ d.entities.length - 3 }} more</template>
            {{ d.entities.every((e) => e.added) ? "added" : "changed" }} ·
          </template>
          <template v-if="d.facts">{{ plural(d.facts, "fact", "facts") }} recorded · </template>
          <template v-if="d.relationships">{{ plural(d.relationships, "relationship", "relationships") }} recorded · </template>
          <template v-if="d.captured"><RouterLink :to="{ name: 'inbox', params: { world: world.slug } }">{{ plural(d.captured, "item", "items") }} captured</RouterLink> · </template>
          <template v-if="d.closed">{{ plural(d.closed, "item", "items") }} closed · </template>
          <template v-if="d.decisions"><RouterLink :to="{ name: 'decisions', params: { world: world.slug } }">{{ plural(d.decisions, "decision", "decisions") }}</RouterLink></template>
        </p>
      </div>
    </section>

    <section v-if="front?.decisions.length" class="card front-section" data-testid="latest-decisions">
      <div class="card-head">
        <h2>Latest decisions</h2>
        <RouterLink class="small" :to="{ name: 'decisions', params: { world: world.slug } }">Decisions</RouterLink>
      </div>
      <ul class="plain-list">
        <li v-for="d in front.decisions" :key="d.id" class="small">
          <span class="muted">{{ journalDay(d.decided_on) }}<template v-if="d.project"> · {{ projectName(d.project) }}</template></span> {{ d.text }}
        </li>
      </ul>
    </section>

    <section v-if="front?.questions.count || unsure" class="card front-section" data-testid="open-questions">
      <div class="card-head"><h2>Open questions</h2></div>
      <ul class="plain-list">
        <li v-for="q in front?.questions.latest ?? []" :key="q.id" class="small">
          <RouterLink :to="{ name: 'item', params: { world: world.slug, id: q.id } }">{{ q.title || q.body.split("\n")[0] }}</RouterLink>
        </li>
      </ul>
      <p v-if="(front?.questions.count ?? 0) > (front?.questions.latest.length ?? 0)" class="small muted">
        {{ front!.questions.count }} open questions<template v-if="front!.questions.oldest"> · oldest from {{ front!.questions.oldest.slice(0, 4) }}</template>
      </p>
      <p v-if="unsure" class="small">
        <RouterLink :to="{ name: 'journal', params: { world: world.slug }, query: { tab: 'loose' } }" data-testid="unsure-count">{{ unsure }} ?? in the Journal</RouterLink>
      </p>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Projects</h2>
        <button v-if="!adding" type="button" class="btn btn-sm" data-testid="new-project" @click="adding = true">New project</button>
      </div>
      <form v-if="adding" class="form" @submit.prevent="addProject">
        <div class="field">
          <label for="p-name">Name</label>
          <input id="p-name" v-model="newName" type="text" maxlength="200" required />
        </div>
        <div class="field">
          <label for="p-kind">Kind</label>
          <select id="p-kind" v-model="newKind">
            <option v-for="k in PROJECT_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </div>
        <div v-if="newError" class="notice error" role="alert">{{ newError }}</div>
        <div class="actions">
          <button class="btn btn-primary" type="submit" :disabled="busy">Add project</button>
          <button class="btn" type="button" @click="adding = false">Cancel</button>
        </div>
      </form>
      <ul v-if="world.projects.length" class="rows">
        <li v-for="(p, i) in world.projects" :key="p.id">
          <RouterLink class="grow" :to="{ name: 'project', params: { world: world.slug, project: p.slug } }">{{ p.name }}</RouterLink>
          <span v-if="projectInfo(p.slug)" class="muted small">
            {{ projectInfo(p.slug)!.words.toLocaleString() }} words<template v-if="projectInfo(p.slug)!.last_written"> · last written {{ fmtAgo(projectInfo(p.slug)!.last_written) }}</template>
          </span>
          <span class="pill">{{ kindLabel(p.kind) }}</span>
          <button type="button" class="icon-btn" :disabled="i === 0" :aria-label="`Move ${p.name} up`" @click="move(i, -1)">
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M3 10l5-5 5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <button type="button" class="icon-btn" :disabled="i === world.projects.length - 1" :aria-label="`Move ${p.name} down`" @click="move(i, 1)">
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </li>
      </ul>
      <p v-else-if="!adding" class="empty">No projects in this world yet.</p>
    </section>
  </template>
</template>
