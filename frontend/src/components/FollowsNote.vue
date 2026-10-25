<script setup lang="ts">
import { computed, nextTick, ref } from "vue";

import { get } from "../api";
import { addFollowup, decisionDay, followOrder, type Follows } from "../followups";
import type { Decision } from "../types";

// Beside a planned fact or relationship, or on a task (docs/SPEC.md §16.1): the decisions it follows ("follows the
// decision of 12 Oct 2026", its text on hover, linking to its line on the Decisions page, or for a task `Follows:
// "…" · 12 Oct 2026`), and "Follows a decision…", which picks one (those tagged with its entries first) to attach to.
const props = defineProps<{
  world: string;
  follows?: Follows[];
  /** the row, to attach it from this side; none: only show what it follows */
  row?: { table: "fact" | "relationship" | "item"; id: string; entities: string[] } | null;
  /** a task's own line ("Follows: …") rather than the quiet note beside a fact */
  task?: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();

const picking = ref(false);
const q = ref("");
const all = ref<Decision[]>([]);
const box = ref<HTMLInputElement | null>(null);
const error = ref("");
const taken = computed(() => new Set((props.follows ?? []).map((f) => f.id)));
const shown = computed(() => {
  const needle = q.value.trim().toLowerCase();
  const pool = followOrder(all.value.filter((d) => !taken.value.has(d.id)), props.row?.entities ?? []);
  return (needle ? pool.filter((d) => d.text.toLowerCase().includes(needle)) : pool).slice(0, 10);
});

async function start() {
  picking.value = true;
  error.value = "";
  try {
    all.value = await get<Decision[]>(`/api/worlds/${encodeURIComponent(props.world)}/decisions`);
  } catch (e) {
    error.value = (e as Error).message;
  }
  await nextTick();
  box.value?.focus();
}
async function pick(d: Decision | undefined) {
  if (!d || !props.row) return;
  try {
    await addFollowup(props.world, d.id, { attach: { table: props.row.table, id: props.row.id } });
    picking.value = false;
    emit("changed");
  } catch (e) {
    error.value = (e as Error).message;
  }
}
const decisionLink = (d: Follows) => ({ name: "decisions", params: { world: props.world }, hash: `#d-${d.id}` });
</script>

<template>
  <span class="follows small" data-testid="follows">
    <template v-for="d in props.follows ?? []" :key="d.id">
      <span v-if="props.task" class="follows-task" data-testid="follows-line">Follows: <RouterLink :to="decisionLink(d)">"{{ d.text }}"</RouterLink> · {{ decisionDay(d.decided_on) }}</span>
      <RouterLink v-else class="muted" :to="decisionLink(d)" :title="d.text" data-testid="follows-line">follows the decision of {{ decisionDay(d.decided_on) }}</RouterLink>
    </template>
    <button v-if="props.row && !picking" type="button" class="linkish small muted" data-testid="follows-pick" @click="start">Follows a decision…</button>
    <span v-if="picking" class="follows-picker">
      <input ref="box" v-model="q" class="filter" placeholder="Which decision?" aria-label="Which decision it follows" @keydown.enter.prevent="pick(shown[0])" @keydown.esc.prevent="picking = false" />
      <ul class="fu-pool">
        <li v-for="d in shown" :key="d.id"><button type="button" class="linkish" @click="pick(d)">{{ d.text }}</button> <span class="muted">· {{ decisionDay(d.decided_on) }}</span></li>
        <li v-if="!shown.length" class="muted">No decision to pick.</li>
      </ul>
      <button type="button" class="linkish small" @click="picking = false">Cancel</button>
    </span>
    <span v-if="error" class="error">{{ error }}</span>
  </span>
</template>
