<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { listCuts, type Cut } from "../cuts";
import { addHarvestNote, getManuscript, getSalvage, reinstateChapter, statusStrength, type ChapterInfo, type SalvageEntry } from "../manuscript";
import { useSession } from "../stores/session";
import NotFoundView from "./NotFoundView.vue";

// What left the book: retired chapters and closed experiments, with notes on what was alive in each, and the cuts
// bin (passages cut from chapters). Nothing here is lost; anything can go back. One search covers both.
const route = useRoute();
const router = useRouter();
const session = useSession();
const world = computed(() => session.world(String(route.params.world)));
const project = computed(() => (world.value ? session.project(world.value.slug, String(route.params.project)) : undefined));
const tab = ref<"retired" | "cuts">(route.query.tab === "cuts" ? "cuts" : "retired");
const q = ref("");
const entries = ref<SalvageEntry[]>([]);
const cuts = ref<Cut[]>([]);
const showPutBack = ref(false);
const error = ref("");
const notice = ref("");
const noting = ref<string | null>(null);
const note = ref("");
let timer: ReturnType<typeof setTimeout> | undefined;

const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });
const fmtTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

async function load() {
  if (!world.value || !project.value) return;
  error.value = "";
  try {
    [entries.value, cuts.value] = await Promise.all([
      getSalvage(world.value.slug, project.value.slug, q.value.trim()),
      listCuts(world.value.slug, project.value.slug, q.value.trim(), showPutBack.value),
    ]);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(project, load, { immediate: true });
watch(showPutBack, load);
watch(q, () => {
  clearTimeout(timer);
  timer = setTimeout(load, 250);
});
watch(tab, (t) => void router.replace({ query: { ...route.query, tab: t === "cuts" ? "cuts" : undefined } }));

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

// ---- cuts: put back (in the source chapter, or one picked), copy ----
const open = ref<string | null>(null);
const placing = ref<string | null>(null);
const target = ref("");
const chapters = ref<ChapterInfo[]>([]);
async function startPutBack(c: Cut) {
  placing.value = c.id;
  target.value = c.chapter && c.chapter.state !== "retired" ? c.chapter.id : "";
  if (!chapters.value.length && world.value && project.value) {
    const m = await getManuscript(world.value.slug, project.value.slug).catch(() => null);
    chapters.value = m ? [...m.chapters, ...m.experiments] : [];
  }
  if (!target.value) target.value = chapters.value[0]?.id ?? "";
}
function putBack(c: Cut) {
  if (!world.value || !project.value || !target.value) return;
  void router.push({ name: "chapter", params: { world: world.value.slug, id: target.value }, query: { putback: c.id, from: project.value.slug } });
}
async function copy(c: Cut) {
  try {
    await navigator.clipboard.writeText(c.body.trim());
    notice.value = "Copied.";
  } catch {
    error.value = "Couldn't copy here; select the text instead.";
  }
}
const strength = (e: SalvageEntry) => (e.status ? statusStrength(e.status.position, Math.max(3, e.status.position + 1)) : 1);
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
        <p class="muted">What left the book: chapters and cut passages. Nothing here is lost; anything can go back.</p>
      </div>
    </div>

    <div class="toolbar">
      <div class="tabs" role="tablist">
        <button type="button" role="tab" class="tab" :aria-selected="tab === 'retired'" data-testid="tab-retired" @click="tab = 'retired'">
          Retired chapters <span class="count">{{ entries.length }}</span>
        </button>
        <button type="button" role="tab" class="tab" :aria-selected="tab === 'cuts'" data-testid="tab-cuts" @click="tab = 'cuts'">
          Cuts <span class="count">{{ cuts.length }}</span>
        </button>
      </div>
      <label for="salvage-search" class="visually-hidden">Search</label>
      <input id="salvage-search" v-model="q" type="search" class="filter search grow" placeholder="Search titles, text, notes and cuts" />
    </div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <div v-if="notice" class="notice ok small" role="status" @click="notice = ''">{{ notice }}</div>

    <template v-if="tab === 'retired'">
      <section v-for="e in entries" :key="e.id" class="card" data-testid="salvage-entry">
        <div class="card-head">
          <h2>
            <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: e.id } }">{{ e.title }}</RouterLink>
            <span v-if="e.status" class="status-pill" :style="{ '--strength': strength(e) }">{{ e.status.label }}</span>
          </h2>
          <span class="muted small">
            {{ e.words.toLocaleString() }} words<template v-if="e.retired_at"> · retired {{ fmt.format(new Date(e.retired_at)) }}</template>
          </span>
        </div>
        <p v-if="e.summary" class="small muted">{{ e.summary }}</p>
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

    <template v-else>
      <label class="check small"><input v-model="showPutBack" type="checkbox" /> Show put back</label>
      <section v-for="c in cuts" :key="c.id" class="card cut-card" :class="{ done: c.put_back_at }" data-testid="cut">
        <div class="card-head">
          <span>
            From
            <RouterLink v-if="c.chapter" :to="{ name: 'chapter', params: { world: world.slug, id: c.chapter.id } }">{{ c.chapter.title }}</RouterLink>
            <template v-else>“{{ c.chapter_title }}” (no longer there)</template>
          </span>
          <span class="muted small">
            {{ fmtTime.format(new Date(c.cut_at)) }} · {{ c.words.toLocaleString() }} words
            <template v-if="c.put_back_at"> · put back {{ fmt.format(new Date(c.put_back_at)) }}<template v-if="c.put_back_to"> into {{ c.put_back_to.title }}</template></template>
          </span>
        </div>
        <p v-if="c.match" class="snippet muted">{{ c.match.before }}<mark>{{ c.match.match }}</mark>{{ c.match.after }}</p>
        <p class="cut-text prose" :class="{ folded: open !== c.id && c.body.length > 400 }" @click="open = open === c.id ? null : c.id">{{ c.body.trim() }}</p>
        <form v-if="placing === c.id" class="actions" @submit.prevent="putBack(c)">
          <label :for="`target-${c.id}`">Put back into</label>
          <select :id="`target-${c.id}`" v-model="target" class="filter">
            <option v-for="ch in chapters" :key="ch.id" :value="ch.id">{{ ch.title }}<template v-if="ch.state === 'experiment'"> (experiment)</template></option>
          </select>
          <button class="btn btn-sm btn-primary" type="submit" :disabled="!target">Open and put back</button>
          <button class="btn btn-sm" type="button" @click="placing = null">Cancel</button>
        </form>
        <div v-else class="actions">
          <button type="button" class="btn btn-sm" @click="startPutBack(c)">Put back</button>
          <button type="button" class="btn btn-sm" @click="copy(c)">Copy</button>
        </div>
      </section>
      <p v-if="!cuts.length && !error" class="empty">{{ q ? "No cut matches." : "The bin is empty. Select text in a chapter and press Ctrl+Shift+X to cut it here." }}</p>
    </template>
  </template>
</template>
