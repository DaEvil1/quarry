<script setup lang="ts">
import { computed, ref } from "vue";

import type { Chapter } from "../manuscript";
import type { EntityRef } from "../types";

// The chapter page's side panel: point of view, the names in the chapter, harvest notes and chapter actions. Its
// own component so that typing (word count, save status) never re-renders it: it changes when the chapter is saved.
const props = defineProps<{ world: string; chapter: Chapter; names: EntityRef[]; readOnly: boolean }>();
const emit = defineEmits<{ pov: [id: string]; checkpoint: []; experiment: [from: "copy" | "scratch"]; retire: [] }>();

const inChapter = computed(() => {
  const counts = new Map<string, { id: string; name: string; kind: string | undefined; count: number }>();
  for (const m of props.chapter.mentions) {
    if (m.kind === "near_miss") continue;
    const c = counts.get(m.entity_id) ?? { id: m.entity_id, name: m.entity_name, kind: m.entity_kind, count: 0 };
    c.count++;
    counts.set(m.entity_id, c);
  }
  return [...counts.values()].sort((a, b) => b.count - a.count);
});
const nearMissCount = computed(() => props.chapter.mentions.filter((m) => m.kind === "near_miss").length);
const characters = computed(() => props.names.filter((n) => n.kind === "character"));
const experimentFrom = ref<"copy" | "scratch">("copy");
</script>

<template>
  <aside class="chapter-side">
    <section>
      <h3 class="small muted">Point of view</h3>
      <select class="filter" aria-label="Point of view" :value="props.chapter.pov?.id ?? ''" :disabled="props.readOnly" @change="emit('pov', ($event.target as HTMLSelectElement).value)">
        <option value="">None</option>
        <option v-for="e in characters" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
    </section>
    <section>
      <h3 class="small muted">In this chapter</h3>
      <ul class="plain-list">
        <li v-for="e in inChapter" :key="e.id" :class="e.kind ? `k-${e.kind}` : ''">
          <RouterLink class="kname" :to="{ name: 'entity', params: { world: props.world, id: e.id } }">{{ e.name }}</RouterLink>
          <span class="muted small">×{{ e.count }}</span>
        </li>
        <li v-if="!inChapter.length" class="muted small">No names from the bible yet.</li>
      </ul>
      <p v-if="nearMissCount" class="small">
        <RouterLink :to="{ name: 'names', params: { world: props.world } }">{{ nearMissCount }} possible misspelling(s)</RouterLink>
      </p>
    </section>
    <section v-if="props.chapter.harvest_notes.length">
      <h3 class="small muted">Harvest notes</h3>
      <p v-for="n in props.chapter.harvest_notes" :key="n.id" class="small">{{ n.body }}</p>
    </section>
    <section class="side-actions">
      <button type="button" class="btn btn-sm" :disabled="props.readOnly" @click="emit('checkpoint')">Checkpoint <kbd>Ctrl S</kbd></button>
      <template v-if="props.chapter.state === 'current'">
        <div class="actions">
          <select v-model="experimentFrom" class="filter" aria-label="Experiment starts from">
            <option value="copy">from a copy</option>
            <option value="scratch">from scratch</option>
          </select>
          <button type="button" class="btn btn-sm" @click="emit('experiment', experimentFrom)">Start an experiment</button>
        </div>
        <button type="button" class="btn btn-sm" @click="emit('retire')">Retire to Salvage</button>
      </template>
    </section>
  </aside>
</template>
