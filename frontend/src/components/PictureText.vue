<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { lookUp, missingReason, pictureUrl, pieces, type Missing } from "../pictures";
import { useViewer } from "../stores/viewer";
import { useCards } from "../world/cards";

// A text shown read-only with its picture lines as pictures, captions under them (docs/SPEC.md §17.3): an entry's
// notes on its page, Read as if accepted. Everything else stays as written.
const props = defineProps<{ text: string; world: string; paragraphs?: boolean }>();
const cards = useCards();
const viewer = useViewer();
const shown = computed(() => pieces(props.text));
const failed = ref(new Set<string>());
const learnt = ref(0);

const WHY: Record<Missing, string> = { deleted: "Picture deleted", elsewhere: "Not a picture of this world", offline: "Not on this device" };
function why(id: string): string | null {
  void learnt.value;
  if (failed.value.has(id)) return typeof navigator !== "undefined" && navigator.onLine === false ? WHY.offline : "Can't be shown";
  const r = missingReason(id);
  if (r) return WHY[r];
  return cards.pictureById.has(id) ? null : cards.cards.length ? "Loading…" : null;
}
watch(
  () => [shown.value, cards.pictures] as const,
  async () => {
    const unknown = shown.value.filter((p) => p.kind === "picture" && !cards.pictureById.has(p.id)).map((p) => (p as { id: string }).id);
    if (unknown.length && cards.cards.length && (await lookUp(props.world, unknown))) learnt.value++;
  },
  { immediate: true },
);
const boxStyle = (id: string) => {
  const p = cards.pictureById.get(id);
  return p ? { aspectRatio: `${p.width} / ${p.height}`, width: `min(100%, ${p.width}px, calc(60vh * ${(p.width / p.height).toFixed(4)}))` } : {};
};
function open(id: string) {
  const all = shown.value.filter((p) => p.kind === "picture" && cards.pictureById.has(p.id)) as { id: string; caption: string }[];
  viewer.show(all.map((p) => ({ id: p.id, caption: p.caption, name: cards.pictureById.get(p.id)?.name ?? "" })), all.findIndex((p) => p.id === id));
}
const paras = (text: string) => text.split("\n").filter((l) => l.trim());
</script>

<template>
  <template v-for="(p, i) in shown" :key="i">
    <template v-if="p.kind === 'text'">
      <template v-if="paragraphs"><p v-for="(l, j) in paras(p.text)" :key="j" class="prose">{{ l }}</p></template>
      <p v-else class="prose item-text">{{ p.text }}</p>
    </template>
    <figure v-else class="picture-figure" data-testid="picture-block" :data-picture="p.id">
      <div v-if="why(p.id)" class="picture-box missing" :class="{ short: !cards.pictureById.has(p.id) }" :style="boxStyle(p.id)"><span class="picture-why">{{ why(p.id) }}</span></div>
      <div v-else class="picture-box opens" :style="boxStyle(p.id)" @click="open(p.id)">
        <img :src="pictureUrl(p.id, 'view')" :alt="p.caption || cards.pictureById.get(p.id)?.name" loading="lazy" decoding="async" @error="failed = new Set([...failed, p.id])" />
      </div>
      <figcaption v-if="p.caption">{{ p.caption }}</figcaption>
    </figure>
  </template>
</template>
