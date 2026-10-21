<script setup lang="ts">
import type { World } from "../types";
import { WORLD_ONLY } from "../types";

// "" = everything in the world, "-" = only what belongs to the whole world, else a project's slug
const model = defineModel<string>({ required: true });
const props = defineProps<{ world: World; id?: string }>();
</script>

<template>
  <label :for="props.id ?? 'project-filter'" class="visually-hidden">Project</label>
  <select :id="props.id ?? 'project-filter'" v-model="model" class="filter">
    <option value="">Everything</option>
    <option :value="WORLD_ONLY">Whole world only</option>
    <option v-for="p in props.world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
  </select>
</template>
