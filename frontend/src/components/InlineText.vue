<script setup lang="ts">
import { nextTick, ref } from "vue";

// Text that edits in place: click (or Enter on it) to edit, Enter or leaving the field saves, Esc cancels.
// `list` names a datalist of values to offer while editing.
const props = withDefaults(defineProps<{ value: string; placeholder?: string; label: string; tag?: string; maxlength?: number; list?: string }>(), {
  placeholder: "",
  tag: "span",
  maxlength: 300,
});
const emit = defineEmits<{ save: [value: string] }>();

const editing = ref(false);
const draft = ref("");
const box = ref<HTMLInputElement | null>(null);

async function start() {
  draft.value = props.value;
  editing.value = true;
  await nextTick();
  box.value?.focus();
  box.value?.select();
}

function done(save: boolean) {
  if (!editing.value) return;
  editing.value = false;
  const v = draft.value.trim();
  if (save && v !== props.value) emit("save", v);
}
</script>

<template>
  <input
    v-if="editing"
    ref="box"
    v-model="draft"
    class="inline-input"
    :class="`inline-${props.tag}`"
    :aria-label="props.label"
    :maxlength="props.maxlength"
    :list="props.list"
    @keydown.enter.prevent="done(true)"
    @keydown.esc.prevent="done(false)"
    @blur="done(true)"
  />
  <component
    :is="props.tag"
    v-else
    class="inline-text"
    :class="{ empty: !props.value }"
    tabindex="0"
    role="button"
    :title="`Edit ${props.label.toLowerCase()}`"
    @click="start"
    @keydown.enter.prevent="start"
    >{{ props.value || props.placeholder }}</component
  >
</template>
