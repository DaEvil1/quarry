<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import type { World } from "../types";

const props = defineProps<{ worlds: World[]; current?: World }>();

const open = ref(false);
const root = ref<HTMLElement | null>(null);
const route = useRoute();

function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false;
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") open.value = false;
}
onMounted(() => {
  document.addEventListener("click", onDocClick);
  document.addEventListener("keydown", onKey);
});
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);
  document.removeEventListener("keydown", onKey);
});
watch(() => route.fullPath, () => (open.value = false));
</script>

<template>
  <div ref="root" class="switcher">
    <button
      type="button"
      class="switcher-btn"
      :aria-expanded="open"
      aria-haspopup="menu"
      data-testid="world-switcher"
      @click="open = !open"
    >
      <span class="label">{{ props.current?.name ?? "Choose a world" }}</span>
      <span class="caret" aria-hidden="true">▼</span>
    </button>
    <div v-if="open" class="switcher-menu" role="menu">
      <RouterLink
        v-for="w in props.worlds"
        :key="w.id"
        :to="{ name: 'world', params: { world: w.slug } }"
        role="menuitem"
        :class="{ current: w.id === props.current?.id }"
        >{{ w.name }}</RouterLink
      >
      <hr v-if="props.worlds.length" />
      <RouterLink :to="{ name: 'new-world' }" role="menuitem">+ New world</RouterLink>
    </div>
  </div>
</template>
