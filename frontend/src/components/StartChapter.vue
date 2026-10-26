<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { del, unreachable } from "../api";
import { followupToast } from "../followups";
import { startChapter } from "../journal";
import { getManuscript, type ChapterInfo } from "../manuscript";
import type { JournalEntry, Project } from "../types";

// Start a chapter from a plan (docs/SPEC.md §18.3): where, in one row (at the end, or after chapter …), then an empty
// chapter there titled as the plan is, linked to it and opened with the plan beside it. A plan with no project asks
// for the project first. The toast (shown by the shell, so it outlives the page) has Undo, which deletes the chapter
// while it is still empty.
const props = defineProps<{ world: string; entry: JournalEntry; projects: Project[] }>();
const emit = defineEmits<{ error: [message: string] }>();
const router = useRouter();

const open = ref(false);
const project = ref(props.entry.project ?? "");
const after = ref("");
const chapters = ref<ChapterInfo[]>([]);
const busy = ref(false);
const fixed = computed(() => !!props.entry.project);

watch(
  [open, project],
  async ([o, p]) => {
    after.value = "";
    chapters.value = [];
    if (o && p) chapters.value = (await getManuscript(props.world, p).catch(() => ({ chapters: [] as ChapterInfo[] }))).chapters;
  },
);

async function start() {
  if (!project.value) return;
  busy.value = true;
  try {
    const ch = await startChapter(props.world, props.entry.id, project.value, after.value || null);
    open.value = false;
    const world = props.world;
    const back = project.value;
    followupToast.value = {
      label: `Chapter ${ch.position + 1}, ${ch.title} · from its plan`,
      undo: async () => {
        await del(`/api/worlds/${encodeURIComponent(world)}/chapters/${ch.id}`);
        await router.push({ name: "project", params: { world, project: back } });
      },
    };
    await router.push({ name: "chapter", params: { world, id: ch.id }, query: { plan: props.entry.id } });
  } catch (e) {
    emit("error", unreachable(e) ? "Starting a chapter needs the network." : (e as Error).message);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <span class="start-chapter">
    <button v-if="!open" type="button" class="linkish" data-testid="start-chapter" @click="open = true">Start a chapter from it</button>
    <form v-else class="actions start-chapter-row" data-testid="start-chapter-row" @submit.prevent="start">
      <select v-if="!fixed" v-model="project" class="filter" aria-label="In which book" data-testid="start-project" required>
        <option value="" disabled>In which book…</option>
        <option v-for="p in projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
      </select>
      <select v-model="after" class="filter" aria-label="Where" data-testid="start-where" :disabled="!project">
        <option value="">at the end</option>
        <option v-for="c in chapters" :key="c.id" :value="c.id">after chapter {{ c.position + 1 }}, {{ c.title }}</option>
      </select>
      <button class="btn btn-sm btn-primary" type="submit" :disabled="busy || !project" data-testid="start-confirm">Start</button>
      <button class="btn btn-sm" type="button" @click="open = false">Cancel</button>
    </form>
  </span>
</template>
