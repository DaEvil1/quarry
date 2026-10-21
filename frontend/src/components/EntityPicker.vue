<script setup lang="ts">
import { computed, nextTick, ref } from "vue";

import type { EntityRef } from "../types";

// Type a few letters of a bible name, pick it with Enter or a tap.
const props = defineProps<{ entities: EntityRef[]; exclude?: string[]; placeholder?: string; autofocus?: boolean }>();
const emit = defineEmits<{ pick: [entity: EntityRef]; cancel: [] }>();

const q = ref("");
const active = ref(0);
const box = ref<HTMLInputElement | null>(null);

const matches = computed(() => {
  const needle = q.value.trim().toLowerCase();
  const pool = props.entities.filter((e) => !props.exclude?.includes(e.id));
  if (!needle) return pool.slice(0, 8);
  const starts = pool.filter((e) => e.name.toLowerCase().startsWith(needle));
  const contains = pool.filter((e) => !starts.includes(e) && e.name.toLowerCase().includes(needle));
  return [...starts, ...contains].slice(0, 8);
});

function pick(e: EntityRef | undefined) {
  if (!e) return;
  emit("pick", e);
  q.value = "";
  active.value = 0;
}

function onKey(e: KeyboardEvent) {
  if (e.key === "ArrowDown") active.value = Math.min(active.value + 1, matches.value.length - 1);
  else if (e.key === "ArrowUp") active.value = Math.max(active.value - 1, 0);
  else if (e.key === "Enter") pick(matches.value[active.value]);
  else if (e.key === "Escape") emit("cancel");
  else return;
  e.preventDefault();
  e.stopPropagation();
}

defineExpose({ focus: () => nextTick(() => box.value?.focus()) });
</script>

<template>
  <div class="picker">
    <label class="visually-hidden" for="entity-picker">Bible entry</label>
    <input
      id="entity-picker"
      ref="box"
      v-model="q"
      type="text"
      autocomplete="off"
      :placeholder="props.placeholder ?? 'Tag with a name from the bible…'"
      :autofocus="props.autofocus"
      @keydown="onKey"
      @input="active = 0"
    />
    <ul v-if="matches.length" class="picker-list" role="listbox">
      <li
        v-for="(e, i) in matches"
        :key="e.id"
        role="option"
        :aria-selected="i === active"
        @mousedown.prevent="pick(e)"
      >
        <span>{{ e.name }}</span><span class="muted small">{{ e.kind }}</span>
      </li>
    </ul>
    <p v-else-if="!props.entities.length" class="muted small">The bible is empty. Add entries under Bible.</p>
  </div>
</template>
