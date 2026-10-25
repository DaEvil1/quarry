<script setup lang="ts">
import { computed } from "vue";

import type { JournalDetail, StoryChapter } from "../types";
import type { Era } from "../world/eras";
import type { Unit } from "../world/when";
import AsOfPicker from "./AsOfPicker.vue";

// The entry tab of the companion panel in a journal entry (docs/SPEC.md §14.1.1): the names in it, its cards' "as of",
// checkpoints and History, and deleting it. Its own component so typing never re-renders it.
const props = defineProps<{
  world: string;
  entry: JournalDetail;
  readOnly: boolean;
  timeline: StoryChapter[];
  unit: Unit;
  times: boolean;
  asof: string;
  at: number | null;
  eraOf?: (t: number | null | undefined) => Era | null;
}>();
const emit = defineEmits<{ checkpoint: []; history: []; asof: [choice: { asof?: string; at?: number }]; remove: [] }>();

const named = computed(() => {
  const counts = new Map<string, { id: string; name: string; kind: string | undefined; count: number }>();
  for (const m of props.entry.mentions) {
    if (m.kind === "near_miss") continue;
    const c = counts.get(m.entity_id) ?? { id: m.entity_id, name: m.entity_name, kind: m.entity_kind, count: 0 };
    c.count++;
    counts.set(m.entity_id, c);
  }
  return [...counts.values()].sort((a, b) => b.count - a.count);
});
</script>

<template>
  <div class="side-chapter" data-testid="journal-side">
    <section>
      <h3 class="small muted">Cards as of</h3>
      <AsOfPicker :timeline="props.timeline" :unit="props.unit" :asof="props.asof" :at="props.at" :times="props.times" :era-of="props.eraOf" testid="entry-as-of" label="Cards as of" @pick="(c) => emit('asof', c)" />
      <p class="small muted">With nothing chosen: the end of the story. Planned facts show too, marked.</p>
    </section>
    <section>
      <h3 class="small muted">In this entry</h3>
      <ul class="plain-list" data-testid="entry-cast">
        <li v-for="e in named" :key="e.id" :class="e.kind ? `k-${e.kind}` : ''">
          <RouterLink class="kname" :to="{ name: 'entity', params: { world: props.world, id: e.id } }">{{ e.name }}</RouterLink>
          <span class="muted small">×{{ e.count }}</span>
        </li>
        <li v-if="!named.length" class="muted small">No names from the bible yet.</li>
      </ul>
    </section>
    <section v-if="!props.readOnly" class="side-actions">
      <button type="button" class="btn btn-sm" @click="emit('checkpoint')">Checkpoint <kbd>Ctrl S</kbd></button>
      <button type="button" class="btn btn-sm" @click="emit('history')">History</button>
      <button type="button" class="btn btn-sm" data-testid="delete-entry" @click="emit('remove')">Delete entry…</button>
    </section>
  </div>
</template>
