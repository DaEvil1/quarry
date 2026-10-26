<script setup lang="ts">
import { computed, nextTick, ref } from "vue";

import { unreachable } from "../api";
import { linkPlan, setEntryAbout, unlinkPlan } from "../journal";
import { getManuscript } from "../manuscript";
import { planChapterText, type JournalEntry, type PlanChapter, type Project } from "../types";
import UndoToast from "./UndoToast.vue";

// A journal entry's head as a plan (docs/SPEC.md §18.1): the Plan switch, and what it is for, `Plan for: chapter 4,
// The Quay · + chapter`, each chapter a chip with ×. Linking marks it; switching Plan off on a linked plan asks first
// and unlinks it. Each change has Undo. These need the network, as the entry's date and project do.
const props = defineProps<{ world: string; entry: JournalEntry; projects: Project[] }>();
const emit = defineEmits<{ changed: [entry: JournalEntry] }>();

const error = ref("");
const asking = ref(false);
const picking = ref(false);
const filter = ref("");
const box = ref<HTMLInputElement | null>(null);
const options = ref<PlanChapter[] | null>(null);
const toast = ref<{ label: string; undo: (() => Promise<void>) | null } | null>(null);

const chapters = computed(() => props.entry.chapters ?? []);
const said = (e: unknown) => (unreachable(e) ? "Plans need the network; try again when you're back online." : (e as Error).message);

async function run(fn: () => Promise<JournalEntry>, label?: string, undo?: () => Promise<JournalEntry>) {
  error.value = "";
  try {
    emit("changed", await fn());
    if (label) toast.value = { label, undo: undo ? async () => emit("changed", await undo()) : null };
  } catch (e) {
    error.value = said(e);
  }
}

function toggle(on: boolean) {
  if (!on && chapters.value.length) {
    asking.value = true;
    return;
  }
  void run(() => setEntryAbout(props.world, props.entry.id, { is_plan: on }));
}
const linkedText = computed(() => chapters.value.map(planChapterText).join(", "));
function unmark() {
  asking.value = false;
  const before = chapters.value.map((c) => c.id);
  void run(
    () => setEntryAbout(props.world, props.entry.id, { is_plan: false }),
    "No longer a plan",
    async () => {
      let out = await setEntryAbout(props.world, props.entry.id, { is_plan: true });
      for (const id of before) out = await linkPlan(props.world, props.entry.id, id);
      return out;
    },
  );
}
function unlink(c: PlanChapter) {
  void run(() => unlinkPlan(props.world, props.entry.id, c.id), `Unlinked from ${planChapterText(c)}`, () => linkPlan(props.world, props.entry.id, c.id));
}
async function openPicker() {
  picking.value = true;
  filter.value = "";
  await nextTick();
  box.value?.focus();
  try {
    // the current chapters and drafts of the plan's project; of every project for a plan with no project
    const projects = props.entry.project ? props.projects.filter((p) => p.slug === props.entry.project) : props.projects;
    const out: PlanChapter[] = [];
    for (const p of projects) {
      const m = await getManuscript(props.world, p.slug);
      for (const c of m.chapters) out.push({ id: c.id, title: c.title, state: "current", project: p.slug, n: c.position + 1 });
      for (const x of m.experiments) for (const d of x.drafts) out.push({ id: d.id, title: d.title, state: "experiment", project: p.slug, n: null });
    }
    options.value = out;
  } catch (e) {
    options.value = [];
    error.value = said(e);
  }
}
const shown = computed(() => {
  const q = filter.value.trim().toLowerCase();
  const have = new Set(chapters.value.map((c) => c.id));
  return (options.value ?? []).filter((c) => !have.has(c.id) && (!q || planChapterText(c).toLowerCase().includes(q))).slice(0, 12);
});
function pick(c: PlanChapter) {
  picking.value = false;
  void run(() => linkPlan(props.world, props.entry.id, c.id), `Plan for ${planChapterText(c)}`, () => unlinkPlan(props.world, props.entry.id, c.id));
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") picking.value = false;
  if (e.key === "Enter" && shown.value[0]) {
    e.preventDefault();
    pick(shown.value[0]);
  }
}
</script>

<template>
  <div class="plan-for" data-testid="plan-head">
    <label class="toggle" title="A plan for chapters, read beside them"><input type="checkbox" :checked="!!entry.is_plan" data-testid="plan-switch" @change="toggle(($event.target as HTMLInputElement).checked)" /> Plan</label>
    <span v-if="entry.is_plan" class="small plan-chapters" data-testid="plan-for">
      <span class="muted">Plan for:</span>
      <span v-for="c in chapters" :key="c.id" class="chip static" :data-chapter="c.id">
        <RouterLink :to="{ name: 'chapter', params: { world, id: c.id }, query: { plan: entry.id } }">{{ planChapterText(c) }}</RouterLink>
        <button type="button" class="chip-x" :aria-label="`Unlink ${planChapterText(c)}`" @click="unlink(c)">×</button>
      </span>
      <span v-if="!chapters.length" class="muted">no chapter yet</span>
      <span class="muted">·</span>
      <span class="plan-pick">
        <button type="button" class="linkish" data-testid="plan-add-chapter" @click="openPicker">+ chapter</button>
        <span v-if="picking" class="status-menu plan-menu" role="listbox" data-testid="plan-chapter-picker">
          <input ref="box" v-model="filter" class="filter" type="search" placeholder="Filter chapters" aria-label="Filter chapters" @keydown="onKey" />
          <span v-if="options === null" class="muted small">Loading…</span>
          <button v-for="c in shown" :key="c.id" type="button" role="option" :data-chapter="c.id" @click="pick(c)">{{ planChapterText(c) }}</button>
          <button type="button" class="quiet" @click="picking = false">Cancel</button>
        </span>
      </span>
    </span>
    <div v-if="asking" class="notice small" role="alertdialog" data-testid="unmark-plan">
      <span>This is the plan for {{ linkedText }}. Unlink it and unmark it?</span>
      <button type="button" class="btn btn-sm" @click="unmark">Unlink and unmark</button>
      <button type="button" class="btn btn-sm" @click="asking = false">Keep it</button>
    </div>
    <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" @dismiss="toast = null" />
  </div>
</template>
