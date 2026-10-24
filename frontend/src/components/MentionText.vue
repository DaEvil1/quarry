<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";

import { fixes } from "../bible";
import { usePrefs } from "../prefs";
import type { Mention, SourceTable } from "../types";
import { useCards } from "../world/cards";
import { hideCard, showCard } from "../world/hovercard";

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

const prefs = usePrefs();
const cards = useCards();
const router = useRouter();
const nameClass = (m: Mention) => (prefs.colourNames && m.entity_kind && !prefs.plainKinds.includes(m.entity_kind) ? `kname k-${m.entity_kind}` : "");
function hover(e: MouseEvent, m: Mention) {
  const to = { name: "entity", params: { world: props.world, id: m.entity_id } };
  showCard(e.currentTarget as HTMLElement, cards.byId.get(m.entity_id), () => void router.push(to), prefs.cardDelay, (kind, label) => cards.several(kind, label));
}
onBeforeUnmount(() => hideCard(true));

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
        :class="nameClass(p.mention)"
        :to="{ name: 'entity', params: { world: props.world, id: p.mention.entity_id } }"
        @mouseenter="hover($event, p.mention)"
        @mouseleave="hideCard()"
        @click.stop="hideCard(true)"
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
