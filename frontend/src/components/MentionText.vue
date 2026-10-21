<script setup lang="ts">
import { computed, ref } from "vue";

import { fixes } from "../bible";
import type { Mention, SourceTable } from "../types";

// A text with its bible names linked and its near misses (likely misspelled names) squiggled. A near miss opens
// the three fixes: replace it here, add it as another spelling of the name, or mark it "not a typo".
const props = defineProps<{ text: string; mentions: Mention[]; world: string; source: { table: SourceTable; id: string } }>();
const emit = defineEmits<{ fixed: [] }>();

type Part = { text: string; mention?: Mention };
const parts = computed<Part[]>(() => {
  const out: Part[] = [];
  let at = 0;
  for (const m of [...props.mentions].sort((a, b) => a.start - b.start)) {
    if (m.start < at || m.end > props.text.length) continue;
    if (m.start > at) out.push({ text: props.text.slice(at, m.start) });
    out.push({ text: props.text.slice(m.start, m.end), mention: m });
    at = m.end;
  }
  if (at < props.text.length) out.push({ text: props.text.slice(at) });
  return out;
});

// the three fixes, as plain functions for the template
const fixReplace = fixes.replace;
const fixSpelling = (world: string, token: string, entityId: string) => fixes.addSpelling(world, token, entityId);
const fixIgnore = fixes.notATypo;

const open = ref<Mention | null>(null);
const busy = ref(false);
const error = ref("");

async function run(fn: () => Promise<unknown>) {
  busy.value = true;
  error.value = "";
  try {
    await fn();
    open.value = null;
    emit("fixed");
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <span class="mention-text">
    <template v-for="(p, i) in parts" :key="i">
      <template v-if="!p.mention">{{ p.text }}</template>
      <RouterLink
        v-else-if="p.mention.kind !== 'near_miss'"
        class="mention"
        :to="{ name: 'entity', params: { world: props.world, id: p.mention.entity_id } }"
        :title="p.mention.kind === 'alias' ? `${p.mention.entity_name} (other spelling)` : p.mention.entity_name"
        @click.stop
        >{{ p.text }}</RouterLink
      >
      <span v-else class="near-miss-wrap"
        ><button
          type="button"
          class="near-miss"
          :aria-expanded="open === p.mention"
          :title="`Did you mean ${p.mention.entity_name}?`"
          @click.stop="open = open === p.mention ? null : p.mention"
        >{{ p.text }}</button
        ><span v-if="open === p.mention" class="fix-menu" role="menu" @click.stop>
          <span class="fix-title">Did you mean <strong>{{ p.mention.entity_name }}</strong>?</span>
          <button
            type="button"
            role="menuitem"
            :disabled="busy"
            @click="run(() => fixReplace(props.world, p.mention!.matched_text, p.mention!.entity_id, props.source))"
          >
            Replace with {{ p.mention.entity_name }}
          </button>
          <button
            type="button"
            role="menuitem"
            :disabled="busy"
            @click="run(() => fixSpelling(props.world, p.mention!.matched_text, p.mention!.entity_id))"
          >
            “{{ p.mention.matched_text }}” is another spelling
          </button>
          <button type="button" role="menuitem" :disabled="busy" @click="run(() => fixIgnore(props.world, p.mention!.matched_text))">
            Not a typo
          </button>
          <span v-if="error" class="fix-error">{{ error }}</span>
        </span></span
      >
    </template>
  </span>
</template>
