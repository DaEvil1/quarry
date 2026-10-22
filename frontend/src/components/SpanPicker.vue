<script setup lang="ts">
import { computed, ref } from "vue";

import type { Span, StoryChapter } from "../types";
import { spanText } from "../world/time";

// When a fact or relationship holds: "always" until set, then "from Storm", "Arrival – Storm"… Click to change.
const props = defineProps<{ span: Span; timeline: StoryChapter[] }>();
const emit = defineEmits<{ save: [span: Span] }>();

const editing = ref(false);
const from = ref("");
const until = ref("");
const titles = computed(() => new Map(props.timeline.map((c) => [c.id, c.title])));
const text = computed(() => spanText(props.span, (id) => titles.value.get(id)));
const projects = computed(() => {
  const out: { name: string; chapters: StoryChapter[] }[] = [];
  for (const c of props.timeline) {
    const last = out[out.length - 1];
    if (last?.name === c.project_name) last.chapters.push(c);
    else out.push({ name: c.project_name, chapters: [c] });
  }
  return out;
});
const backwards = computed(() => {
  const i = (id: string) => props.timeline.find((c) => c.id === id)?.index;
  return !!from.value && !!until.value && (i(from.value) ?? 0) > (i(until.value) ?? 0);
});

function start() {
  from.value = props.span.from_chapter_id ?? "";
  until.value = props.span.until_chapter_id ?? "";
  editing.value = true;
}
function save() {
  editing.value = false;
  emit("save", { from_chapter_id: from.value || null, until_chapter_id: until.value || null });
}
</script>

<template>
  <span v-if="!editing" class="span-text" :class="{ always: !text }">
    <button type="button" class="linkish small" :title="props.timeline.length ? 'When it holds' : 'Add chapters to date things'" :disabled="!props.timeline.length" @click="start">
      {{ text || "always" }}
    </button>
  </span>
  <form v-else class="span-form" @submit.prevent="save" @keydown.esc.prevent="editing = false">
    <label class="small muted">from
      <select v-model="from" class="filter" aria-label="From chapter">
        <option value="">the start</option>
        <optgroup v-for="p in projects" :key="p.name" :label="p.name">
          <option v-for="c in p.chapters" :key="c.id" :value="c.id">{{ c.title }}</option>
        </optgroup>
      </select>
    </label>
    <label class="small muted">until
      <select v-model="until" class="filter" aria-label="Until chapter">
        <option value="">the end</option>
        <optgroup v-for="p in projects" :key="p.name" :label="p.name">
          <option v-for="c in p.chapters" :key="c.id" :value="c.id">{{ c.title }}</option>
        </optgroup>
      </select>
    </label>
    <button class="btn btn-sm btn-primary" type="submit" :disabled="backwards" :title="backwards ? '“From” comes after “until”' : ''">Set</button>
    <button class="btn btn-sm" type="button" @click="editing = false">Cancel</button>
  </form>
</template>
