<script setup lang="ts">
import { originLine } from "../journal";
import type { ItemOrigin } from "../types";

// Where an item came from (docs/SPEC.md §14.3.1): "From the Journal, 2 March 2019" or "From the chapter “The Quay”",
// with the passage quoted and a link into the editor at the passage (found by its text there).
const props = defineProps<{ world: string; origin: ItemOrigin }>();
const to = () => ({
  name: props.origin.table === "journal" ? "journal-entry" : "chapter",
  params: { world: props.world, id: props.origin.id },
  query: props.origin.passage ? { passage: props.origin.passage } : {},
});
</script>

<template>
  <div class="item-origin small" data-testid="item-origin">
    <RouterLink :to="to()">{{ originLine(props.origin) }}</RouterLink>
    <blockquote v-if="props.origin.passage" class="muted passage-quote">{{ props.origin.passage }}</blockquote>
  </div>
</template>
