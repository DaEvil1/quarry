<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { journalDay, type SinceThis } from "../journal";
import type { JournalDetail, StoryChapter } from "../types";
import type { Era } from "../world/eras";
import type { Unit } from "../world/when";
import AsOfPicker from "./AsOfPicker.vue";
import { castOf } from "../world/cast";

// The entry tab of the companion panel in a journal entry (docs/SPEC.md §14.1.1): the names in it, its cards' "as of",
// checkpoints and History, and deleting it. Its own component so typing never re-renders it.
const props = defineProps<{
  world: string;
  entry: JournalDetail;
  readOnly: boolean;
  timeline: StoryChapter[];
  unit: Unit;
  times: boolean;
  asof: string;
  at: number | null;
  eraOf?: (t: number | null | undefined) => Era | null;
  /** the note for next time (docs/SPEC.md §14.4), and what happened since it was written (§14.5) */
  note: string;
  since: SinceThis | null;
}>();
const emit = defineEmits<{ checkpoint: []; history: []; asof: [choice: { asof?: string; at?: number }]; remove: []; note: [text: string] }>();
const openSince = ref(false);
const noteDraft = ref(props.note);
watch(() => props.note, (n) => (noteDraft.value = n));
const names = computed(() => {
  const s = props.since;
  if (!s) return "";
  const list = s.entities.map((x) => x.entity.name);
  return list.length > 2 ? `${list.slice(0, 2).join(", ")} and ${list.length - 2} more` : list.join(" and ");
});

// shared names nothing settles are listed once, with their claimants (docs/SPEC.md §14.10)
const cast = computed(() => castOf(props.entry.mentions));
const named = computed(() => cast.value.named);
</script>

<template>
  <div class="side-chapter" data-testid="journal-side">
    <section data-testid="entry-note">
      <h3 class="small muted"><label for="entry-next-note">A note for next time</label></h3>
      <input id="entry-next-note" v-model="noteDraft" class="filter" type="text" maxlength="2000" placeholder="What's next?" @change="emit('note', noteDraft)" />
    </section>
    <section v-if="props.since && (props.since.decisions || props.since.changes || props.since.later || props.since.edited)" data-testid="since-this">
      <h3 class="small muted">Since this was written</h3>
      <p class="small">
        <button type="button" class="linkish" @click="openSince = !openSince">
          <template v-if="props.since.decisions || props.since.changes">{{ props.since.decisions }} decision{{ props.since.decisions === 1 ? "" : "s" }} and {{ props.since.changes }} change{{ props.since.changes === 1 ? "" : "s" }} touch {{ names }}</template>
          <template v-if="props.since.later"> · {{ props.since.later }} later note{{ props.since.later === 1 ? "" : "s" }}</template>
        </button>
      </p>
      <p v-if="props.since.edited" class="small muted">written {{ journalDay(props.since.date) }} · last edited {{ props.since.edited }}</p>
      <div v-if="openSince" class="since-list">
        <div v-for="x in props.since.entities" :key="x.entity.id" class="small">
          <RouterLink class="kname" :class="`k-${x.entity.kind}`" :to="{ name: 'entity', params: { world: props.world, id: x.entity.id } }">{{ x.entity.name }}</RouterLink>
          <ul class="plain-list">
            <li v-for="d in x.decisions" :key="d.id"><span class="muted">{{ d.date }}</span> “{{ d.text }}”</li>
            <li v-for="(c, i) in x.changes" :key="i">{{ c.what }} · <span class="muted">{{ c.date }}</span></li>
            <li v-if="x.later">
              {{ x.later }} later note{{ x.later === 1 ? "" : "s" }} name{{ x.later === 1 ? "s" : "" }} {{ x.entity.name }} ·
              <RouterLink :to="{ name: 'entity-read', params: { world: props.world, id: x.entity.id }, query: { in: 'planning', from: props.since.date } }">Read them</RouterLink>
            </li>
          </ul>
        </div>
      </div>
    </section>
    <section>
      <h3 class="small muted">Cards as of</h3>
      <AsOfPicker :timeline="props.timeline" :unit="props.unit" :asof="props.asof" :at="props.at" :times="props.times" :era-of="props.eraOf" testid="entry-as-of" label="Cards as of" @pick="(c) => emit('asof', c)" />
      <p class="small muted">With nothing chosen: the end of the story. Planned facts show too, marked.</p>
    </section>
    <section>
      <h3 class="small muted">In this entry</h3>
      <ul class="plain-list" data-testid="entry-cast">
        <li v-for="e in named" :key="e.id" :class="e.kind ? `k-${e.kind}` : ''">
          <RouterLink class="kname" :to="{ name: 'entity', params: { world: props.world, id: e.id } }">{{ e.name }}</RouterLink>
          <span class="muted small">×{{ e.count }}</span>
        </li>
        <li v-for="u in cast.unsettled" :key="`${u.form}|${u.claimants.map((c) => c.id).join()}`" data-testid="cast-unsettled" :title="`Not settled: ${u.claimants.map((c) => c.name).join(' or ')}`">
          <span class="muted">{{ u.form }}?</span>{{ " " }}
          <template v-for="(c, i) in u.claimants" :key="c.id"><span v-if="i" class="muted"> · </span><RouterLink class="kname" :class="c.kind ? `k-${c.kind}` : ''" :to="{ name: 'entity', params: { world: props.world, id: c.id } }">{{ u.short[i] }}</RouterLink></template>
          <span class="muted small">×{{ u.count }}</span>
        </li>
        <li v-if="!named.length && !cast.unsettled.length" class="muted small">No names from the bible yet.</li>
      </ul>
    </section>
    <section v-if="!props.readOnly" class="side-actions">
      <button type="button" class="btn btn-sm" @click="emit('checkpoint')">Checkpoint <kbd>Ctrl S</kbd></button>
      <button type="button" class="btn btn-sm" @click="emit('history')">History</button>
      <button type="button" class="btn btn-sm" data-testid="delete-entry" @click="emit('remove')">Delete entry…</button>
    </section>
  </div>
</template>
