<script setup lang="ts">
import { computed, ref } from "vue";

import type { Cut } from "../cuts";
import type { About, Chapter, StatusRef } from "../manuscript";
import type { EntityRef, Presence, TimeValue } from "../types";
import type { Era } from "../world/eras";
import type { Unit } from "../world/when";
import InlineText from "./InlineText.vue";
import TimeField from "./TimeField.vue";
import { castOf } from "../world/cast";

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
  /** the world's unit of time, and the time this chapter carries on from when it has none of its own */
  unit?: Unit;
  carried?: string;
  carriedAt?: number | null;
  eraOf?: (t: number | null | undefined) => Era | null;
}>();
const placeOf = computed(() => new Map(props.presence.map((p) => [p.entity_id, p.place])));
const emit = defineEmits<{
  pov: [id: string];
  checkpoint: [];
  experiment: [from: "copy" | "scratch"];
  retire: [];
  about: [about: { summary?: string; status_id?: string | null }];
  when: [about: About];
  putBack: [cut: Cut, where: "place" | "cursor"];
  copy: [cut: Cut];
  since: [label: string];
}>();

// shared names nothing settles are listed once, with their claimants (docs/SPEC.md §14.10)
const cast = computed(() => castOf(props.chapter.mentions));
const inChapter = computed(() => cast.value.named);
const nearMissCount = computed(() => props.chapter.mentions.filter((m) => m.kind === "near_miss").length);
const characters = computed(() => props.names.filter((n) => n.kind === "character"));
const experimentFrom = ref<"copy" | "scratch">("copy");
const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const open = ref<string | null>(null);
</script>

<template>
  <div class="side-chapter">
    <section data-testid="chapter-about">
      <h3 class="small muted">In one line</h3>
      <p class="small side-summary">
        <InlineText :value="props.chapter.summary" label="Summary" placeholder="Add a one-line summary" :maxlength="300" @save="(v) => emit('about', { summary: v })" />
      </p>
      <h3 class="small muted"><label for="chapter-status">Status</label></h3>
      <select id="chapter-status" class="filter" :value="props.chapter.status?.id ?? ''" @change="emit('about', { status_id: ($event.target as HTMLSelectElement).value || null })">
        <option value="">none</option>
        <option v-for="s in props.statuses" :key="s.id" :value="s.id">{{ s.label }}</option>
      </select>
      <h3 class="small muted">Set in</h3>
      <p class="small" data-testid="side-when">
        <TimeField :value="{ time_at: props.chapter.time_at ?? null, time_end: props.chapter.time_end, time_label: props.chapter.time_label, time_approx: props.chapter.time_approx, outside_time: props.chapter.outside_time } as TimeValue" :unit="props.unit ?? { unit: 'year', units: 'years' }" label="Set in" :carried="props.carried" :carried-at="props.carriedAt ?? null" :era-of="props.eraOf" @save="(v) => emit('when', v)" />
      </p>
      <h3 class="small muted"><label for="chapter-told-as">Told as</label></h3>
      <select id="chapter-told-as" class="filter" :value="props.chapter.told_as ?? ''" data-testid="told-as-select" @change="emit('when', { told_as: (($event.target as HTMLSelectElement).value || null) as 'flashback' | 'tale' | null })">
        <option value="">the present of the story</option>
        <option value="flashback">a flashback</option>
        <option value="tale">a tale (told by a character)</option>
      </select>
    </section>
    <section>
      <h3 class="small muted">Point of view</h3>
      <select class="filter" aria-label="Point of view" :value="props.chapter.pov?.id ?? ''" :disabled="props.readOnly" @change="emit('pov', ($event.target as HTMLSelectElement).value)">
        <option value="">None</option>
        <option v-for="e in characters" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
    </section>
    <section v-if="!props.readOnly" data-testid="changes-since">
      <h3 class="small muted"><label for="changes-since">Show changes since</label></h3>
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
        <li v-for="u in cast.unsettled" :key="`${u.form}|${u.claimants.map((c) => c.id).join()}`" data-testid="cast-unsettled" :title="`Not settled: ${u.claimants.map((c) => c.name).join(' or ')}`">
          <span class="muted">{{ u.form }}?</span>{{ " " }}
          <template v-for="(c, i) in u.claimants" :key="c.id"><span v-if="i" class="muted"> · </span><RouterLink class="kname" :class="c.kind ? `k-${c.kind}` : ''" :to="{ name: 'entity', params: { world: props.world, id: c.id } }">{{ u.short[i] }}</RouterLink></template>
          <span class="muted small">×{{ u.count }}</span>
        </li>
        <li v-if="!inChapter.length && !cast.unsettled.length" class="muted small">No names from the bible yet.</li>
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
