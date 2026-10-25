<script setup lang="ts">
import { computed } from "vue";

import { journalDay } from "../journal";

// Where a fact or relationship was planned (docs/SPEC.md §14.1.2): "planned in the Journal, 2 March 2019 · What the
// Guild wants", linking into the entry at the passage (found by its text; if it can't be found, the entry opens at
// the top and the line says the passage changed). Never a place in the story.
const props = defineProps<{
  world: string;
  entry: { id: string; date: string; title: string | null; body: string } | undefined;
  passage: string | null | undefined;
}>();
const changed = computed(() => !!props.entry && !!props.passage && !props.entry.body.includes(props.passage));
</script>

<template>
  <span v-if="props.entry" class="planned-in small muted" data-testid="planned-in">
    planned in the Journal,
    <RouterLink :to="{ name: 'journal-entry', params: { world: props.world, id: props.entry.id }, query: props.passage && !changed ? { passage: props.passage } : {} }">{{ journalDay(props.entry.date) }}<template v-if="props.entry.title"> · {{ props.entry.title }}</template></RouterLink>
    <span v-if="changed" class="pill warn">passage changed</span>
  </span>
</template>
