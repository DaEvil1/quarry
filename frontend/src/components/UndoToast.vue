<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";

// A short-lived "Accepted · Undo" line at the bottom of the screen after an item is moved (or a passage cut, a name
// kept…), with Undo and any other actions that go with it.
const props = withDefaults(
  defineProps<{ label: string | null; undo: (() => Promise<void>) | null; actions?: { label: string; run: () => unknown }[]; ms?: number }>(),
  { actions: () => [], ms: 6000 },
);
const emit = defineEmits<{ dismiss: []; undone: [] }>();
const busy = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;

watch(
  () => props.label,
  (label) => {
    clearTimeout(timer);
    if (label) timer = setTimeout(() => emit("dismiss"), props.ms);
  },
);
onBeforeUnmount(() => clearTimeout(timer));

async function doUndo() {
  if (!props.undo) return;
  busy.value = true;
  try {
    await props.undo();
    emit("undone");
  } finally {
    busy.value = false;
    emit("dismiss");
  }
}

async function run(fn: () => unknown) {
  busy.value = true;
  try {
    await fn();
  } finally {
    busy.value = false;
    emit("dismiss");
  }
}
</script>

<template>
  <div v-if="props.label" class="toast" role="status" data-testid="toast">
    <span>{{ props.label }}</span>
    <button v-for="a in props.actions" :key="a.label" type="button" class="linkish" :disabled="busy" @click="run(a.run)">{{ a.label }}</button>
    <button v-if="props.undo" type="button" class="linkish" :disabled="busy" @click="doUndo">Undo</button>
  </div>
</template>
