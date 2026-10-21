<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";

// A short-lived "Accepted · Undo" line at the bottom of the screen after an item is moved.
const props = defineProps<{ label: string | null; undo: (() => Promise<void>) | null }>();
const emit = defineEmits<{ dismiss: []; undone: [] }>();
const busy = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;

watch(
  () => props.label,
  (label) => {
    clearTimeout(timer);
    if (label) timer = setTimeout(() => emit("dismiss"), 6000);
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
</script>

<template>
  <div v-if="props.label" class="toast" role="status">
    <span>{{ props.label }}</span>
    <button v-if="props.undo" type="button" class="linkish" :disabled="busy" @click="doUndo">Undo</button>
  </div>
</template>
