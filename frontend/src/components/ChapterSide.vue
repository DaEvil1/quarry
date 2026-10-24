<script setup lang="ts">
import { computed, ref } from "vue";

import type { Cut } from "../cuts";
import { statusStrength, type Chapter, type StatusRef } from "../manuscript";
import type { EntityRef, Presence } from "../types";
import InlineText from "./InlineText.vue";

// The chapter tab of the companion panel: summary and status, point of view, changes since a checkpoint, the names
// in the chapter, cuts from it, harvest notes and chapter actions. Its own component so that typing (word count,
// save status) never re-renders it: it changes when the chapter is saved, or when typing pauses.
const props = defineProps<{
  world: string;
  chapter: Chapter;
  names: EntityRef[];
  readOnly: boolean;
  presence: Presence[];
  statuses: StatusRef[];
  cuts: (Cut & { waiting?: boolean })[];
  /** changes since a checkpoint: the labels there are, the one chosen, and what the panel says about it */
  since: { labels: string[]; chosen: string; line: string; revising: boolean };
}>();
const placeOf = computed(() => new Map(props.presence.map((p) => [p.entity_id, p.place])));
const emit = defineEmits<{
  pov: [id: string];
  checkpoint: [];
  experiment: [from: "copy" | "scratch"];
  retire: [];
  about: [about: { summary?: string; status_id?: string | null }];
  putBack: [cut: Cut, where: "place" | "cursor"];
  copy: [cut: Cut];
  since: [label: string];
}>();

const inChapter = computed(() => {
  const counts = new Map<string, { id: string; name: string; kind: string | undefined; count: number }>();
  for (const m of props.chapter.mentions) {
    if (m.kind === "near_miss") continue;
    const c = counts.get(m.entity_id) ?? { id: m.entity_id, name: m.entity_name, kind: m.entity_kind, count: 0 };
    c.count++;
    counts.set(m.entity_id, c);
  }
  return [...counts.values()].sort((a, b) => b.count - a.count);
});
const nearMissCount = computed(() => props.chapter.mentions.filter((m) => m.kind === "near_miss").length);
const characters = computed(() => props.names.filter((n) => n.kind === "character"));
const experimentFrom = ref<"copy" | "scratch">("copy");
const strength = (s: StatusRef) => statusStrength(s.position, props.statuses.length || s.position + 1);
const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const open = ref<string | null>(null);
</script>

<template>
  <div class="side-chapter">
    <section data-testid="chapter-about">
      <h3 class="small muted">In one line</h3>
      <p class="small chapter-summary">
        <InlineText :value="props.chapter.summary" label="Summary" placeholder="Add a one-line summary" :maxlength="300" @save="(v) => emit('about', { summary: v })" />
      </p>
      <div class="actions">
        <label class="small muted" for="chapter-status">Status</label>
        <select id="chapter-status" class="filter" :value="props.chapter.status?.id ?? ''" @change="emit('about', { status_id: ($event.target as HTMLSelectElement).value || null })">
          <option value="">none</option>
          <option v-for="s in props.statuses" :key="s.id" :value="s.id">{{ s.label }}</option>
        </select>
        <span v-if="props.chapter.status" class="status-pill" :style="{ '--strength': strength(props.chapter.status) }">{{ props.chapter.status.label }}</span>
      </div>
    </section>
    <section>
      <h3 class="small muted">Point of view</h3>
      <select class="filter" aria-label="Point of view" :value="props.chapter.pov?.id ?? ''" :disabled="props.readOnly" @change="emit('pov', ($event.target as HTMLSelectElement).value)">
        <option value="">None</option>
        <option v-for="e in characters" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
    </section>
    <section v-if="!props.readOnly" data-testid="changes-since">
      <label class="small muted" for="changes-since">Show changes since</label>
      <select id="changes-since" class="filter" :value="props.since.chosen" @change="emit('since', ($event.target as HTMLSelectElement).value)">
        <option value="">nothing</option>
        <option v-if="props.since.chosen && !props.since.labels.includes(props.since.chosen)" :value="props.since.chosen">{{ props.since.chosen }}</option>
        <option v-for="l in props.since.labels" :key="l" :value="l">{{ l }}</option>
      </select>
      <p v-if="props.since.chosen && !props.since.revising" class="small muted">Shown while Revising.</p>
      <p v-else-if="props.since.line" class="small" data-testid="changes-line">{{ props.since.line }}</p>
    </section>
    <section>
      <h3 class="small muted">In this chapter</h3>
      <ul class="plain-list">
        <li v-for="e in inChapter" :key="e.id" :class="e.kind ? `k-${e.kind}` : ''">
          <RouterLink class="kname" :to="{ name: 'entity', params: { world: props.world, id: e.id } }">{{ e.name }}</RouterLink>
          <span v-if="placeOf.get(e.id)" class="small at" :class="`k-${placeOf.get(e.id)!.kind}`">at <span class="kname">{{ placeOf.get(e.id)!.name }}</span></span>
          <span class="muted small">×{{ e.count }}</span>
        </li>
        <li v-if="!inChapter.length" class="muted small">No names from the bible yet.</li>
      </ul>
      <p v-if="nearMissCount" class="small">
        <RouterLink :to="{ name: 'names', params: { world: props.world } }">{{ nearMissCount }} possible misspelling(s)</RouterLink>
      </p>
    </section>
    <section v-if="props.cuts.length" data-testid="chapter-cuts">
      <h3 class="small muted">Cut from this chapter</h3>
      <div v-for="c in props.cuts" :key="c.id" class="cut small" data-testid="chapter-cut">
        <div class="muted">{{ fmt.format(new Date(c.cut_at)) }} · {{ c.words }} words<template v-if="c.waiting"> · waiting to sync</template></div>
        <p class="cut-text" :class="{ folded: open !== c.id && c.body.length > 160 }" @click="open = open === c.id ? null : c.id">{{ c.body.trim() }}</p>
        <div class="qrow">
          <button type="button" class="qchip" :disabled="props.readOnly || c.waiting" @click="emit('putBack', c, 'place')">Put back where it was</button>
          <button type="button" class="qchip quiet" :disabled="props.readOnly || c.waiting" @click="emit('putBack', c, 'cursor')">Insert at cursor</button>
          <button type="button" class="qchip quiet" @click="emit('copy', c)">Copy</button>
        </div>
      </div>
    </section>
    <section v-if="props.chapter.harvest_notes.length">
      <h3 class="small muted">Harvest notes</h3>
      <p v-for="n in props.chapter.harvest_notes" :key="n.id" class="small">{{ n.body }}</p>
    </section>
    <section class="side-actions">
      <button type="button" class="btn btn-sm" :disabled="props.readOnly" @click="emit('checkpoint')">Checkpoint <kbd>Ctrl S</kbd></button>
      <template v-if="props.chapter.state === 'current'">
        <div class="actions">
          <select v-model="experimentFrom" class="filter" aria-label="Experiment starts from">
            <option value="copy">from a copy</option>
            <option value="scratch">from scratch</option>
          </select>
          <button type="button" class="btn btn-sm" @click="emit('experiment', experimentFrom)">Start an experiment</button>
        </div>
        <button type="button" class="btn btn-sm" @click="emit('retire')">Retire to Salvage</button>
      </template>
      <p v-if="!props.readOnly" class="small muted">Select text and press <kbd>Ctrl Shift X</kbd> to cut it to the bin. <kbd>Ctrl Shift H</kbd> finds in all chapters.</p>
    </section>
  </div>
</template>
