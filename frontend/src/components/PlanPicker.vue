<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";

import { journalDay, listJournal } from "../journal";
import type { JournalEntry } from "../types";

// "Link a plan…" (docs/SPEC.md §18.1): the journal entries, plans with no chapter yet first, then other plans, then
// other entries, newest first within each; type to filter.
const props = defineProps<{ world: string; exclude?: string[] }>();
const emit = defineEmits<{ pick: [entry: JournalEntry]; close: [] }>();

const all = ref<JournalEntry[] | null>(null);
const filter = ref("");
const error = ref("");
const box = ref<HTMLInputElement | null>(null);

onMounted(async () => {
  await nextTick();
  box.value?.focus();
  try {
    all.value = await listJournal(props.world);
  } catch (e) {
    all.value = [];
    error.value = (e as Error).message;
  }
});
const rank = (e: JournalEntry) => (e.is_plan ? ((e.chapters ?? []).length ? 1 : 0) : 2);
const shown = computed(() => {
  const q = filter.value.trim().toLowerCase();
  const skip = new Set(props.exclude ?? []);
  return (all.value ?? [])
    .filter((e) => !skip.has(e.id) && (!q || `${e.title ?? ""}\n${e.body}`.toLowerCase().includes(q)))
    .sort((a, b) => rank(a) - rank(b) || b.entry_date.localeCompare(a.entry_date))
    .slice(0, 40);
});
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") emit("close");
  if (e.key === "Enter" && shown.value[0]) {
    e.preventDefault();
    emit("pick", shown.value[0]);
  }
}
</script>

<template>
  <div class="picker-overlay" role="dialog" aria-modal="true" aria-label="Link a plan" data-testid="plan-picker" @click.self="emit('close')">
    <div class="card picker">
      <div class="card-head">
        <h2>Link a plan</h2>
        <button type="button" class="btn btn-sm" aria-label="Close" @click="emit('close')">×</button>
      </div>
      <input ref="box" v-model="filter" class="filter" type="search" placeholder="Filter the Journal" aria-label="Filter the Journal" @keydown="onKey" />
      <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
      <p v-if="all === null" class="muted small">Loading…</p>
      <p v-else-if="!shown.length" class="empty">No journal entry matches.</p>
      <ul v-else class="rows">
        <li v-for="e in shown" :key="e.id">
          <button type="button" class="linkish grow plan-pick-row" :data-entry="e.id" data-testid="plan-picker-entry" @click="emit('pick', e)">
            <strong>{{ e.title || "Untitled" }}</strong>
            <span class="muted small"> · {{ journalDay(e.entry_date) }}</span>
            <span v-if="e.is_plan" class="muted small"> · {{ (e.chapters ?? []).length ? "plan" : "plan, no chapter yet" }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>
