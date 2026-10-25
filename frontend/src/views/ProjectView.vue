<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get, patch, unreachable } from "../api";
import InlineText from "../components/InlineText.vue";
import RetireReview from "../components/RetireReview.vue";
import TimeField from "../components/TimeField.vue";
import UndoToast from "../components/UndoToast.vue";
import WordHistoryChart from "../components/WordHistory.vue";
import { age, listItems } from "../items";
import {
  addDraft,
  checkpointAll,
  closeRange,
  createChapter,
  getManuscript,
  getSalvage,
  getWordHistory,
  orderDrafts,
  reorderChapters,
  retireMany,
  reviewLine,
  setAbout,
  setRange,
  startRange,
  statusStrength,
  statuses as statusApi,
  undoReview,
  type About,
  type ChapterInfo,
  type ChapterStatus,
  type Choice,
  type Experiment,
  type Manuscript,
  type Reviewed,
  type StatusRef,
  type WordHistory,
} from "../manuscript";
import { localManuscript } from "../offline";
import { useSession } from "../stores/session";
import { PROJECT_KINDS, firstLine, kindLabel, localToday, type Item, type Project, type ProjectKind, type StoryChapter, type World } from "../types";
import { useCards } from "../world/cards";
import { chapterWhen, unitOf } from "../world/when";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();

const world = computed(() => session.world(String(route.params.world)));
const project = computed(() =>
  world.value ? session.project(world.value.slug, String(route.params.project)) : undefined,
);

const manuscript = ref<Manuscript | null>(null);
// the server couldn't be reached: the chapters kept on this device
const offlineCopy = ref(false);
const openItems = ref<Item[]>([]);
const error = ref("");

async function load() {
  const w = world.value;
  const p = project.value;
  if (!w || !p) return;
  error.value = "";
  offlineCopy.value = false;
  try {
    [manuscript.value, openItems.value] = await Promise.all([
      getManuscript(w.slug, p.slug),
      listItems(w.slug, { project: p.slug, limit: 20 }),
    ]);
    void loadStatuses();
    getWordHistory(w.slug, p.slug).then((h) => (history.value = h), () => (history.value = null));
  } catch (e) {
    if (unreachable(e)) {
      manuscript.value = await localManuscript(w.slug, p.slug);
      offlineCopy.value = true;
    } else {
      error.value = (e as Error).message;
    }
  }
}
watch(project, load, { immediate: true });
watch(() => world.value?.slug, (w) => w && void cards.load(w), { immediate: true });

// ---- when each chapter is set (docs/SPEC.md §13.1.2): edited in place, muted after the summary ----
const unit = computed(() => unitOf(world.value));
const story = computed(() => new Map(cards.timeline.map((c) => [c.id, c])));
/** A chapter's time as the clock reads it: its own, or the one it carries on from (from the cards' timeline). */
function storyOf(c: ChapterInfo): StoryChapter {
  const s = story.value.get(c.id);
  return { id: c.id, title: c.title, project: c.project, project_name: "", index: 0, ...(s ?? {}), time_at: c.time_at ?? null, time_end: c.time_end, time_label: c.time_label, time_approx: c.time_approx, outside_time: c.outside_time, told_as: c.told_as };
}
const carried = (c: ChapterInfo) => {
  const w = chapterWhen(storyOf(c), unit.value);
  return w.own ? "" : w.text;
};
/** Own time earlier than the chapter before it, with no mark: a quiet hint, one click to mark it a flashback. */
function setEarlier(i: number): boolean {
  const list = manuscript.value?.chapters ?? [];
  const c = list[i];
  const prev = list[i - 1];
  if (!c || !prev || c.told_as || c.time_at == null || c.outside_time) return false;
  const before = prev.time_at ?? story.value.get(prev.id)?.set_time ?? null;
  return before !== null && c.time_at < before;
}
async function setTime(c: ChapterInfo, about: About) {
  await aboutChange(c, about);
  void cards.refresh(world.value?.slug);
}

// ---- restructuring (docs/SPEC.md §13.6): a range picked with Shift-click, experiments across it, and the review
// before anything leaves the book ----
const selected = ref<string[]>([]);
let anchor: string | null = null;
function pickRow(c: ChapterInfo, e: MouseEvent) {
  const list = manuscript.value?.chapters ?? [];
  if (e.shiftKey && anchor) {
    const a = list.findIndex((x) => x.id === anchor);
    const b = list.findIndex((x) => x.id === c.id);
    selected.value = list.slice(Math.min(a, b), Math.max(a, b) + 1).map((x) => x.id);
  } else {
    selected.value = selected.value.length === 1 && selected.value[0] === c.id ? [] : [c.id];
    anchor = c.id;
  }
  starting.value = null;
}
const picked = computed(() => (manuscript.value?.chapters ?? []).filter((c) => selected.value.includes(c.id)));
const numberOf = (id: string) => (manuscript.value?.chapters ?? []).findIndex((c) => c.id === id) + 1;
const rangeText = (ids: string[]) => {
  const ns = ids.map(numberOf).filter((n) => n > 0).sort((a, b) => a - b);
  return ns.length > 1 ? `${ns[0]}–${ns[ns.length - 1]}` : String(ns[0] ?? "");
};
const starting = ref<null | "range" | "before" | "after">(null);
const newTitle2 = ref("");
const startFrom = ref<"copy" | "scratch">("copy");
function beginStart(kind: "range" | "before" | "after") {
  starting.value = kind;
  newTitle2.value = kind === "range" ? "New beginning" : "New chapters";
  startFrom.value = "copy";
}
async function doStart() {
  const w = world.value;
  const p = project.value;
  if (!w || !p || !starting.value || !newTitle2.value.trim()) return;
  error.value = "";
  try {
    const first = picked.value[0]!;
    const last = picked.value[picked.value.length - 1]!;
    const out = await startRange(w.slug, p.slug, starting.value === "range"
      ? { title: newTitle2.value, start: startFrom.value, range: picked.value.map((c) => c.id) }
      : { title: newTitle2.value, start: "scratch", insert: { chapter_id: (starting.value === "before" ? first : last).id, side: starting.value } });
    starting.value = null;
    selected.value = [];
    open.value = out.id;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// experiments: under the last chapter of their range, or at the place they add at
const experiments = computed(() => manuscript.value?.experiments ?? []);
const inRange = computed(() => new Set(experiments.value.flatMap((x) => x.range.map((r) => r.id))));
const rangeEnd = (x: Experiment) => [...x.range].reverse().find((r) => (manuscript.value?.chapters ?? []).some((c) => c.id === r.id))?.id;
const experimentsAfter = (id: string) => experiments.value.filter((x) => (x.range.length ? rangeEnd(x) === id : x.insert?.side === "after" && x.insert.chapter_id === id));
const experimentsBefore = (id: string) => experiments.value.filter((x) => !x.range.length && x.insert?.side === "before" && x.insert.chapter_id === id);
const placed = computed(() => new Set((manuscript.value?.chapters ?? []).flatMap((c) => [...experimentsAfter(c.id), ...experimentsBefore(c.id)].map((x) => x.id))));
const orphanExperiments = computed(() => experiments.value.filter((x) => !placed.value.has(x.id)));
const short2 = (n: number) => (n < 1000 ? String(n) : `${(n / 1000).toFixed(1)}k`);
function experimentLine(x: Experiment): string {
  const drafts = `${x.drafts.length} draft${x.drafts.length === 1 ? "" : "s"} (${short2(x.words)})`;
  if (x.range.length) return `${x.title} · replaces ${rangeText(x.range.map((r) => r.id))} (${short2(x.range_words)} words) · ${drafts}`;
  if (x.insert) return `${x.title} · adds ${x.drafts.length} draft${x.drafts.length === 1 ? "" : "s"} ${x.insert.side} chapter ${numberOf(x.insert.chapter_id)}`;
  return `${x.title} · ${drafts}`;
}
const open = ref<string | null>(null);
const draftTitle = ref("");
const copyFrom = ref("");
const retiredChapters = ref<{ id: string; title: string }[]>([]);
async function openExperiment(x: Experiment) {
  open.value = open.value === x.id ? null : x.id;
  if (open.value && world.value && project.value) {
    retiredChapters.value = (await getSalvage(world.value.slug, project.value.slug).catch(() => [])).map((s) => ({ id: s.id, title: s.title }));
  }
}
async function newDraft(x: Experiment) {
  const w = world.value;
  if (!w) return;
  try {
    await addDraft(w.slug, x.id, copyFrom.value ? { copy_from: copyFrom.value } : { title: draftTitle.value.trim() || undefined });
    draftTitle.value = copyFrom.value = "";
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
async function moveDraft(x: Experiment, i: number, by: -1 | 1) {
  const w = world.value;
  if (!w) return;
  const ids = x.drafts.map((d) => d.id);
  const [d] = ids.splice(i, 1);
  ids.splice(i + by, 0, d!);
  await orderDrafts(w.slug, x.id, ids).catch((e: Error) => (error.value = e.message));
  await load();
}
async function newRange(x: Experiment) {
  const w = world.value;
  if (!w || !picked.value.length) return;
  try {
    await setRange(w.slug, x.id, { range: picked.value.map((c) => c.id) });
    selected.value = [];
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// the review before chapters leave: retiring a selection, a draft, or closing an experiment
const reviewing = ref<null | { chapters: { id: string; title: string }[]; verb: string; experiment?: Experiment; outcome?: "accepted" | "harvested" | "rejected" }>(null);
const decision = ref("");
const targets = computed(() => {
  const leaving = new Set(reviewing.value?.chapters.map((c) => c.id) ?? []);
  const staying = (manuscript.value?.chapters ?? []).filter((c) => !leaving.has(c.id)).map((c) => ({ id: c.id, title: c.title }));
  const drafts = reviewing.value?.outcome === "accepted" ? (reviewing.value.experiment?.drafts ?? []).map((d) => ({ id: d.id, title: `${d.title} (draft)` })) : [];
  return [...drafts, ...staying];
});
function retireSelected() {
  reviewing.value = { chapters: picked.value.map((c) => ({ id: c.id, title: c.title })), verb: picked.value.length > 1 ? `Retire ${picked.value.length} chapters` : "Retire" };
}
function retireDraft(d: ChapterInfo) {
  reviewing.value = { chapters: [{ id: d.id, title: d.title }], verb: "Remove the draft" };
}
function closeExp(x: Experiment, outcome: "accepted" | "harvested" | "rejected") {
  const leaving = outcome === "accepted" ? x.range.filter((r) => r.state === "current") : x.drafts;
  reviewing.value = { chapters: leaving.map((c) => ({ id: c.id, title: c.title })), verb: { accepted: "Accept", harvested: "Harvest", rejected: "Reject" }[outcome], experiment: x, outcome };
  decision.value = "";
}
const toast = ref<{ label: string; undo: () => Promise<void> } | null>(null);
async function reviewed(review: Choice[], notes: Record<string, string>) {
  const w = world.value;
  const r = reviewing.value;
  if (!w || !r) return;
  error.value = "";
  try {
    let done: Reviewed;
    if (r.experiment && r.outcome) {
      done = await closeRange(w.slug, r.experiment.id, { outcome: r.outcome, review, notes, decision: decision.value || undefined, decided_on: localToday() });
      notice.value = done.said?.join(" ") ?? "";
    } else {
      done = await retireMany(w.slug, r.chapters.map((c) => c.id), review, notes);
    }
    reviewing.value = null;
    selected.value = [];
    const what = r.outcome === "accepted" ? `Accepted “${r.experiment?.title}”` : r.outcome ? `${r.verb}ed “${r.experiment?.title}”` : `Retired ${r.chapters.length === 1 ? `“${r.chapters[0]!.title}”` : `${r.chapters.length} chapters`}`;
    toast.value = {
      label: `${what} · ${reviewLine(done.summary)}`,
      undo: async () => {
        await undoReview(w.slug, done.id);
        await load();
        void cards.refresh(w.slug);
      },
    };
    await load();
    void cards.refresh(w.slug);
  } catch (e) {
    error.value = (e as Error).message;
  }
}

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

// ---- summaries and statuses (docs/SPEC.md §11.2) ----
const statusList = ref<ChapterStatus[]>([]);
const shownStatuses = computed<StatusRef[]>(() => (statusList.value.length ? statusList.value : (manuscript.value?.statuses ?? [])));
const strength = (s: StatusRef) => statusStrength(s.position, shownStatuses.value.length || s.position + 1);
const picking = ref<string | null>(null);
async function loadStatuses() {
  const w = world.value;
  const p = project.value;
  if (!w || !p) return;
  statusList.value = await statusApi.list(w.slug, p.slug).catch(() => statusList.value);
}
async function about(c: ChapterInfo, changes: { summary?: string; status_id?: string | null }) {
  await aboutChange(c, changes);
}
async function aboutChange(c: ChapterInfo, changes: About) {
  const w = world.value;
  if (!w) return;
  picking.value = null;
  error.value = "";
  try {
    await setAbout(w.slug, c.id, changes);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
/** "9 raw (31k) · 4 rewritten (14k) · 2 none" */
const tally = computed(() =>
  (manuscript.value?.status_tally ?? [])
    .filter((t) => t.chapters)
    .map((t) => (t.label === null ? `${t.chapters} none` : `${t.chapters} ${t.label} (${short(t.words)})`))
    .join(" · "),
);
const short = (n: number) => (n < 1000 ? String(n) : `${Math.round(n / 1000)}k`);

async function statusChange(fn: () => Promise<ChapterStatus[]>) {
  error.value = "";
  try {
    statusList.value = await fn();
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
function renameStatus(s: ChapterStatus, label: string) {
  const w = world.value;
  if (w && label) void statusChange(() => statusApi.rename(w.slug, s.id, label));
}
const newStatus = ref("");
function addStatus() {
  const w = world.value;
  const p = project.value;
  const label = newStatus.value.trim();
  newStatus.value = "";
  if (w && p && label) void statusChange(() => statusApi.add(w.slug, p.slug, label));
}
function moveStatus(i: number, by: -1 | 1) {
  const w = world.value;
  const p = project.value;
  if (!w || !p) return;
  const ids = statusList.value.map((s) => s.id);
  const [x] = ids.splice(i, 1);
  ids.splice(i + by, 0, x!);
  void statusChange(() => statusApi.order(w.slug, p.slug, ids));
}
function removeStatus(s: ChapterStatus) {
  const w = world.value;
  if (!w) return;
  if (s.chapters && !confirm(`${s.chapters} ${s.chapters === 1 ? "chapter has" : "chapters have"} “${s.label}”. ${s.chapters === 1 ? "It goes" : "They go"} back to no status. Remove it?`)) return;
  void statusChange(() => statusApi.remove(w.slug, s.id));
}

// ---- word history (§11.5) and a checkpoint of every chapter (§11.6) ----
const history = ref<WordHistory | null>(null);
const checkpointing = ref(false);
const checkpointLabel = ref("");
const notice = ref("");
async function checkpointEvery() {
  const w = world.value;
  const p = project.value;
  const label = checkpointLabel.value.trim();
  if (!w || !p || !label) return;
  error.value = "";
  try {
    const r = await checkpointAll(w.slug, p.slug, label);
    checkpointing.value = false;
    checkpointLabel.value = "";
    notice.value = `Checkpoint “${r.label}” kept in ${r.chapters} ${r.chapters === 1 ? "chapter" : "chapters"}.`;
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// ---- rename ----
const editing = ref(false);
const name = ref("");
const slug = ref("");
const kind = ref<ProjectKind>("novel");
// how many chapters without an entry make a gap on its mentions strip (docs/SPEC.md §12.1)
const gap = ref(5);
watch(project, () => (editing.value = false));

function startEdit() {
  if (!project.value) return;
  name.value = project.value.name;
  slug.value = project.value.slug;
  kind.value = project.value.kind;
  gap.value = project.value.gap_chapters ?? 5;
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
      gap_chapters: gap.value,
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
        <RouterLink class="btn btn-sm" :to="{ name: 'replace', params: { world: world.slug, project: project.slug } }">Find and replace</RouterLink>
        <button type="button" class="btn btn-sm" @click="(checkpointing = !checkpointing), (checkpointLabel = '')">Checkpoint every chapter…</button>
        <button v-if="!editing" type="button" class="btn btn-sm" @click="startEdit">Edit</button>
      </div>
    </div>

    <form v-if="checkpointing" class="card actions" data-testid="checkpoint-all" @submit.prevent="checkpointEvery">
      <label for="checkpoint-all">Label for a checkpoint of every chapter and experiment</label>
      <input id="checkpoint-all" v-model="checkpointLabel" class="filter grow" type="text" maxlength="200" placeholder="before the polish" required />
      <button class="btn btn-sm btn-primary" type="submit">Keep</button>
      <button class="btn btn-sm" type="button" @click="checkpointing = false">Cancel</button>
    </form>
    <div v-if="notice" class="notice ok small" role="status" @click="notice = ''">{{ notice }}</div>

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
        <label for="p-gap">Gap length</label>
        <input id="p-gap" v-model.number="gap" type="number" min="1" max="999" required />
        <div class="hint">On an entry's mentions strip, this many chapters without it, between two that name it, make a gap.</div>
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
    <div v-if="offlineCopy" class="notice offline small" role="status" data-testid="manuscript-offline">
      Offline: the chapters kept on this device. Reordering and new chapters wait until you're back.
    </div>

    <section class="card">
      <div class="card-head"><h2>Manuscript</h2></div>
      <div v-if="selected.length" class="selection-bar" data-testid="selection-bar">
        <span class="small">{{ selected.length === 1 ? `Chapter ${rangeText(selected)}` : `Chapters ${rangeText(selected)}` }} picked <span class="muted">(Shift-click to pick a range)</span></span>
        <button type="button" class="btn btn-sm" data-testid="start-experiment" @click="beginStart('range')">Start an experiment…</button>
        <button type="button" class="btn btn-sm" data-testid="add-before" @click="beginStart('before')">Add chapters before…</button>
        <button type="button" class="btn btn-sm" data-testid="add-after" @click="beginStart('after')">Add chapters after…</button>
        <button type="button" class="btn btn-sm" data-testid="retire-selected" @click="retireSelected">Retire…</button>
        <button type="button" class="btn btn-sm quiet" @click="selected = []">Clear</button>
      </div>
      <form v-if="starting" class="card actions start-form" data-testid="start-form" @submit.prevent="doStart" @keydown.esc.prevent="starting = null">
        <label class="small" for="exp-title">{{ starting === "range" ? `An experiment replacing ${rangeText(selected)}` : `New chapters ${starting} chapter ${rangeText(selected.slice(starting === "before" ? 0 : -1))}` }}</label>
        <input id="exp-title" v-model="newTitle2" class="filter grow" maxlength="300" required aria-label="Experiment title" />
        <select v-if="starting === 'range'" v-model="startFrom" class="filter" aria-label="Start from">
          <option value="copy">from copies</option>
          <option value="scratch">from scratch</option>
        </select>
        <button class="btn btn-sm btn-primary" type="submit">Start</button>
        <button class="btn btn-sm" type="button" @click="starting = null">Cancel</button>
      </form>
      <ol class="chapters" data-testid="chapters">
        <template v-for="(c, i) in manuscript?.chapters ?? []" :key="c.id">
          <li v-for="x in experimentsBefore(c.id)" :key="x.id" class="chapter-row experiment" data-testid="experiment-row">
            <button type="button" class="linkish grow" @click="openExperiment(x)">↳ {{ experimentLine(x) }}</button>
          </li>
          <li
            class="chapter-row"
            :class="{ dragging: dragging === c.id, picked: selected.includes(c.id), 'in-range': inRange.has(c.id) }"
            draggable="true"
            :data-testid="`chapter-${i + 1}`"
            @dragstart="dragging = c.id"
            @dragend="dragging = null"
            @dragover.prevent
            @drop.prevent="drop(c.id)"
          >
            <span class="drag" aria-hidden="true">⋮⋮</span>
            <button type="button" class="muted small chapter-no linkish" :aria-label="`Pick chapter ${i + 1}`" :aria-pressed="selected.includes(c.id)" @click="pickRow(c, $event)">{{ i + 1 }}</button>
            <span class="grow chapter-name">
              <span class="chapter-head">
              <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: c.id } }">{{ c.title }}</RouterLink>
              <span v-if="c.told_as" class="pill told-as" data-testid="told-as">{{ c.told_as }}</span>
              <span class="status-at">
                <button type="button" class="status-pill" :class="{ unset: !c.status }" :style="c.status ? { '--strength': strength(c.status) } : {}"
                  :aria-label="`Status of ${c.title}: ${c.status?.label ?? 'none'}`" data-testid="status-pill" :disabled="offlineCopy"
                  @click="picking = picking === c.id ? null : c.id">{{ c.status?.label ?? "status" }}</button>
                <span v-if="picking === c.id" class="status-menu" role="menu" data-testid="status-menu">
                  <button v-for="s in shownStatuses" :key="s.id" type="button" role="menuitem" class="status-pill" :style="{ '--strength': strength(s) }" @click="about(c, { status_id: s.id })">{{ s.label }}</button>
                  <button type="button" role="menuitem" class="status-pill unset" @click="about(c, { status_id: null })">none</button>
                </span>
              </span>
              </span>
              <span v-if="manuscript?.cast?.[c.id]?.length" class="cast small" data-testid="cast">
                <span v-for="x in manuscript.cast[c.id]" :key="x.id" class="kname" :class="`k-${x.kind}`" :title="`${x.name}: named ${x.count}×`">{{ x.name }}</span>
              </span>
              <span class="chapter-summary small muted" data-testid="chapter-summary">
                <InlineText v-if="!offlineCopy" :value="c.summary" :label="`Summary of ${c.title}`" placeholder="+ one line" :maxlength="300" @save="(v) => about(c, { summary: v })" />
                <template v-else>{{ c.summary }}</template>
              </span>
              <span class="chapter-when small muted" data-testid="chapter-when">
                <TimeField :value="{ time_at: c.time_at ?? null, time_end: c.time_end, time_label: c.time_label, time_approx: c.time_approx, outside_time: c.outside_time }" :unit="unit" :label="`When ${c.title} is set`" placeholder="+ when" :carried="carried(c)" :carried-at="storyOf(c).set_time ?? null" :era-of="cards.eraOf" :disabled="offlineCopy" @save="(v) => setTime(c, v)" />
                <span v-if="setEarlier(i)" class="set-earlier small" data-testid="set-earlier">set earlier · <button type="button" class="linkish" @click="setTime(c, { told_as: 'flashback' })">mark it a flashback</button></span>
              </span>
            </span>
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
          <li v-for="x in experimentsAfter(c.id)" :key="x.id" class="chapter-row experiment" data-testid="experiment-row">
            <button type="button" class="linkish grow" @click="openExperiment(x)">↳ {{ experimentLine(x) }}</button>
          </li>
        </template>
        <li v-for="x in orphanExperiments" :key="x.id" class="chapter-row experiment" data-testid="experiment-row">
          <button type="button" class="linkish grow" @click="openExperiment(x)">↳ {{ experimentLine(x) }}</button>
        </li>
      </ol>
      <template v-for="x in experiments" :key="`open-${x.id}`">
        <section v-if="open === x.id" class="card experiment-card" data-testid="experiment">
          <div class="card-head">
            <h3>{{ x.title }}</h3>
            <span class="actions">
              <RouterLink class="btn btn-sm" :to="{ name: 'read', params: { world: world.slug, project: project.slug }, query: { as_if: x.id } }" data-testid="read-as-if">Read as if accepted</RouterLink>
              <button type="button" class="btn btn-sm btn-primary" data-testid="accept" @click="closeExp(x, 'accepted')">Accept</button>
              <button type="button" class="btn btn-sm" @click="closeExp(x, 'harvested')">Harvest</button>
              <button type="button" class="btn btn-sm" @click="closeExp(x, 'rejected')">Reject</button>
            </span>
          </div>
          <p v-if="x.lost.length" class="notice warn small" data-testid="lost">
            {{ x.lost.length }} of its chapters {{ x.lost.length === 1 ? "was" : "were" }} replaced{{ x.replaced_by ? ` by “${x.replaced_by}”` : "" }}.
            <button v-if="selected.length" type="button" class="linkish" @click="newRange(x)">Give it chapters {{ rangeText(selected) }} instead</button>
            <span v-else class="muted">Pick the chapters it should replace now, then give it them.</span>
          </p>
          <ol class="chapters drafts" data-testid="drafts">
            <li v-for="(d, j) in x.drafts" :key="d.id" class="chapter-row" data-testid="draft">
              <span class="muted small chapter-no">{{ j + 1 }}</span>
              <span class="grow chapter-name">
                <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: d.id } }">{{ d.title }}</RouterLink>
                <span class="chapter-summary small muted">
                  <InlineText :value="d.summary" :label="`Summary of ${d.title}`" placeholder="+ one line" :maxlength="300" @save="(v) => about(d, { summary: v })" />
                  <TimeField :value="{ time_at: d.time_at ?? null, time_end: d.time_end, time_label: d.time_label, time_approx: d.time_approx, outside_time: d.outside_time }" :unit="unit" :label="`When ${d.title} is set`" :era-of="cards.eraOf" @save="(v) => setTime(d, v)" />
                </span>
              </span>
              <span v-if="d.status" class="status-pill" :style="{ '--strength': strength(d.status) }">{{ d.status.label }}</span>
              <span class="muted small chapter-words">{{ d.words.toLocaleString() }} w</span>
              <button type="button" class="icon-btn" :disabled="j === 0" :aria-label="`Move draft ${d.title} up`" @click="moveDraft(x, j, -1)">↑</button>
              <button type="button" class="icon-btn" :disabled="j === x.drafts.length - 1" :aria-label="`Move draft ${d.title} down`" @click="moveDraft(x, j, 1)">↓</button>
              <button type="button" class="icon-btn" :aria-label="`Remove draft ${d.title}`" @click="retireDraft(d)">×</button>
            </li>
          </ol>
          <form class="actions" data-testid="new-draft" @submit.prevent="newDraft(x)">
            <input v-model="draftTitle" class="filter grow" maxlength="300" placeholder="New draft title" aria-label="New draft title" :disabled="!!copyFrom" />
            <select v-model="copyFrom" class="filter" aria-label="Copy a chapter in">
              <option value="">or copy a chapter in…</option>
              <optgroup label="In the book">
                <option v-for="c in manuscript?.chapters ?? []" :key="c.id" :value="c.id">{{ c.title }}</option>
              </optgroup>
              <optgroup v-if="retiredChapters.length" label="Salvage">
                <option v-for="c in retiredChapters" :key="c.id" :value="c.id">{{ c.title }}</option>
              </optgroup>
            </select>
            <button class="btn btn-sm" type="submit">{{ copyFrom ? "Copy in" : "New draft" }}</button>
          </form>
        </section>
      </template>
      <template v-if="reviewing">
        <div v-if="reviewing.outcome === 'accepted' || reviewing.outcome === 'rejected'" class="field">
          <label for="close-decision2" class="small">Decision (optional)</label>
          <input id="close-decision2" v-model="decision" class="filter" type="text" maxlength="1000" />
        </div>
        <RetireReview :world="world.slug" :chapters="reviewing.chapters" :experiment="reviewing.outcome === 'accepted' ? reviewing.experiment?.id : undefined" :targets="targets" :verb="reviewing.verb" @done="reviewed" @cancel="reviewing = null" />
      </template>
      <p v-if="manuscript && !manuscript.chapters.length" class="empty">No chapters yet.</p>
      <form class="actions new-chapter" @submit.prevent="addChapter">
        <label for="new-chapter" class="visually-hidden">New chapter title</label>
        <input id="new-chapter" v-model="newTitle" class="filter grow" type="text" maxlength="300" placeholder="New chapter title" />
        <button class="btn btn-primary btn-sm" type="submit" :disabled="!newTitle.trim()">Add chapter</button>
      </form>
    </section>

    <div class="tallies">
      <section v-if="manuscript?.pov_tally.length" class="card">
        <div class="card-head"><h2>Point of view</h2></div>
        <ul class="rows" data-testid="pov-tally">
          <li v-for="p in manuscript.pov_tally" :key="p.name">
            <span class="grow">{{ p.name }}</span>
            <span class="muted small">{{ p.chapters }} {{ p.chapters === 1 ? "chapter" : "chapters" }}</span>
          </li>
        </ul>
      </section>
      <section v-if="manuscript?.chapters.length" class="card">
        <div class="card-head"><h2>Status</h2></div>
        <p class="small" data-testid="status-tally">{{ tally }}</p>
      </section>
    </div>

    <WordHistoryChart v-if="history" :history="history" />
    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" :ms="15000" @dismiss="toast = null" />

    <section v-if="statusList.length || !offlineCopy" class="card" data-testid="statuses">
      <div class="card-head">
        <h2>Chapter statuses</h2>
        <span class="muted small">From the first to the last stage; each pill gets stronger along the way.</span>
      </div>
      <ul class="rows">
        <li v-for="(s, i) in statusList" :key="s.id">
          <span class="status-pill" :style="{ '--strength': strength(s) }" aria-hidden="true">&nbsp;</span>
          <span class="grow"><InlineText :value="s.label" :label="`Status ${s.label}`" :maxlength="100" @save="(v) => renameStatus(s, v)" /></span>
          <span class="muted small">{{ s.chapters }} {{ s.chapters === 1 ? "chapter" : "chapters" }}</span>
          <button type="button" class="icon-btn" :disabled="i === 0" :aria-label="`Move ${s.label} up`" @click="moveStatus(i, -1)">↑</button>
          <button type="button" class="icon-btn" :disabled="i === statusList.length - 1" :aria-label="`Move ${s.label} down`" @click="moveStatus(i, 1)">↓</button>
          <button type="button" class="icon-btn" :aria-label="`Remove ${s.label}`" @click="removeStatus(s)">×</button>
        </li>
      </ul>
      <form class="actions" @submit.prevent="addStatus">
        <label for="new-status" class="visually-hidden">New status</label>
        <input id="new-status" v-model="newStatus" class="filter grow" type="text" maxlength="100" placeholder="New status" />
        <button class="btn btn-sm" type="submit" :disabled="!newStatus.trim()">Add</button>
      </form>
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
