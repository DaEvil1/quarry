<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { addFact, deleteFact, setLabelSwitches, updateFact, type KindSuggestions } from "../bible";
import PlannedIn from "./PlannedIn.vue";
import { ENTITY_KINDS, type Entity, type Fact, type Span, type Standing, type StoryChapter } from "../types";
import { filterText } from "../world/labels";
import { factsAsOf, norm, type At, type IndexOf } from "../world/time";
import type { Era } from "../world/eras";
import type { Unit } from "../world/when";
import InlineText from "./InlineText.vue";
import SpanPicker from "./SpanPicker.vue";

// An entry's facts: labelled values, added in one line, edited in place. Typing a label offers the kind's common and
// suggested labels; typing a value offers the values already used for that label on the same kind (docs/SPEC.md
// §12.6.1). A label that holds several values shows them as chips side by side (§12.6.4).
const props = defineProps<{
  world: string;
  entity: Entity;
  facts: Fact[];
  suggestions: KindSuggestions;
  /** does this label hold several values at once for the entry's kind? */
  several: (label: string) => boolean;
  chapterTitles: Record<string, string>;
  /** the journal entries facts were planned in (docs/SPEC.md §14.1.2) */
  journalEntries?: Record<string, { id: string; date: string; title: string | null; body: string }>;
  timeline: StoryChapter[];
  /** "as of" a point on the clock: facts that don't hold then are dimmed */
  asOf: At | null;
  indexOf: IndexOf;
  unit?: Unit;
  eraOf?: (t: number | null | undefined) => Era | null;
}>();
const emit = defineEmits<{ changed: []; error: [message: string] }>();
const route = useRoute();
const router = useRouter();

const label = ref("");
const value = ref("");
const newStanding = ref<Standing>("planned");
const labelBox = ref<HTMLInputElement | null>(null);
const valueBox = ref<HTMLInputElement | null>(null);
const STANDINGS: Standing[] = ["canon", "planned", "rumour"];
const has = computed(() => new Set(props.facts.map((f) => norm(f.label))));
const unused = computed(() => props.suggestions.labels.filter((s) => !has.value.has(norm(s))));
// common labels for the kind (on three or more of its entries) that this entry hasn't got: one click to start one
const offer = computed(() => props.suggestions.common.filter((s) => !has.value.has(norm(s))));
const kindPlural = computed(() => ENTITY_KINDS.find((k) => k.value === props.entity.kind)?.plural.toLowerCase() ?? props.entity.kind);

// one list of values per label shown or being typed, so a value field offers that label's values
const valueLists = computed(() => {
  const labels = new Map<string, string>();
  for (const l of [...props.facts.map((f) => f.label), label.value]) if (l.trim()) labels.set(norm(l), `fact-values-${labels.size}`);
  return labels;
});
const valuesOf = (l: string) => props.suggestions.values[norm(l)] ?? [];
const listFor = (l: string) => valueLists.value.get(norm(l));

// the one-time question when this entry's new fact brought its label to three entries of the kind (§12.6.5): a line
// under the facts that takes no focus and blocks nothing
const prompt = ref<{ label: string; count: number; expected: boolean } | null>(null);

async function run(fn: () => Promise<unknown>) {
  try {
    await fn();
    emit("changed");
  } catch (e) {
    emit("error", (e as Error).message);
  }
}

function add() {
  if (!label.value.trim()) return;
  // added on the entry page, a fact is planned until it is in the book or marked canon (docs/SPEC.md §14.1.2)
  const body = { label: label.value, value: value.value, standing: newStanding.value };
  label.value = value.value = "";
  newStanding.value = "planned";
  prompt.value = null;
  labelBox.value?.focus();
  void run(async () => {
    const f = await addFact(props.world, props.entity.id, body);
    if (f.prompt) prompt.value = { label: f.prompt.label, count: f.prompt.count, expected: false };
  });
}

function start(l: string) {
  label.value = l;
  prompt.value = null;
  void nextTick(() => valueBox.value?.focus());
}
// "Add it" on a missing label opens the fact with its value suggestions
watch(
  () => route.query.add,
  (l) => {
    if (typeof l !== "string" || !l) return;
    start(l);
    const { add: _, ...rest } = route.query;
    void router.replace({ query: rest });
  },
  { immediate: true },
);

async function expectIt() {
  const p = prompt.value;
  if (!p) return;
  try {
    await setLabelSwitches(props.world, props.entity.kind, p.label, { expected: true });
    p.expected = true;
    emit("changed");
  } catch (e) {
    emit("error", (e as Error).message);
  }
}

const set = (f: Fact, changes: Partial<Fact>) => run(() => updateFact(props.world, f, changes));
const setSpan = (f: Fact, span: Span) => set(f, span);
const now = computed(() => (props.asOf === null ? null : new Set(factsAsOf(props.facts, props.asOf, props.indexOf, props.several).map((f) => f.id))));

// rows: one per fact, except a label with several values, whose facts share a row as chips
const rows = computed(() => {
  const out: { label: string; facts: Fact[]; several: boolean }[] = [];
  for (const f of props.facts) {
    if (props.several(f.label)) {
      const row = out.find((r) => r.several && norm(r.label) === norm(f.label));
      if (row) {
        row.facts.push(f);
        continue;
      }
      out.push({ label: f.label, facts: [f], several: true });
    } else out.push({ label: f.label, facts: [f], several: false });
  }
  return out;
});
// every entry of the kind with this value, in the bible's table
const filterLink = (f: Fact) => ({ name: "bible-kind", params: { world: props.world, kind: props.entity.kind }, query: { f: filterText({ label: f.label, value: f.value }) } });
</script>

<template>
  <section class="card" data-testid="facts">
    <div class="card-head">
      <h2>Facts</h2>
      <span class="muted small">Anything worth keeping straight. Leave out what you don't know.</span>
    </div>
    <table v-if="props.facts.length" class="facts">
      <tbody>
        <tr v-for="r in rows" :key="r.facts[0]!.id" :class="{ off: !r.several && now && !now.has(r.facts[0]!.id), several: r.several }" :title="!r.several && now && !now.has(r.facts[0]!.id) ? 'Not true at this point in the story' : ''">
          <th>
            <InlineText v-if="!r.several" :value="r.label" label="Label" :maxlength="100" @save="(v) => v && set(r.facts[0]!, { label: v })" />
            <template v-else>{{ r.label }} <span class="muted small" title="This label holds several values at once">(several)</span></template>
          </th>
          <td v-if="!r.several" class="grow">
            <InlineText :value="r.facts[0]!.value" label="Value" placeholder="—" :maxlength="5000" :list="listFor(r.label)" @save="(v) => set(r.facts[0]!, { value: v })" />
            <RouterLink v-if="r.facts[0]!.value.trim()" class="value-filter small" :to="filterLink(r.facts[0]!)" :title="`Every ${props.entity.kind} with ${r.label}: ${r.facts[0]!.value}`" :aria-label="`Every ${props.entity.kind} with ${r.label}: ${r.facts[0]!.value}`">≡</RouterLink>
            <SpanPicker :span="r.facts[0]!" :timeline="props.timeline" :unit="props.unit" :era-of="props.eraOf" @save="(sp) => setSpan(r.facts[0]!, sp)" />
            <div class="evidence small muted">
              <InlineText
                :value="r.facts[0]!.evidence ?? ''"
                label="Evidence"
                placeholder="+ where it says so"
                :maxlength="5000"
                @save="(v) => set(r.facts[0]!, { evidence: v || null })"
              /><template v-if="r.facts[0]!.evidence && r.facts[0]!.established_in_chapter_id"> — {{ props.chapterTitles[r.facts[0]!.established_in_chapter_id] ?? "a chapter" }}</template>
            </div>
            <PlannedIn v-if="r.facts[0]!.planned_in_journal_id" :world="props.world" :entry="props.journalEntries?.[r.facts[0]!.planned_in_journal_id]" :passage="r.facts[0]!.planned_evidence" />
          </td>
          <td v-else class="grow" :colspan="3">
            <div class="value-chips" data-testid="value-chips">
              <span v-for="f in r.facts" :key="f.id" class="chip static value-chip" :class="[f.standing, { off: now && !now.has(f.id) }]" data-testid="value-chip">
                <InlineText :value="f.value" label="Value" placeholder="—" :maxlength="5000" :list="listFor(r.label)" @save="(v) => set(f, { value: v })" />
                <SpanPicker :span="f" :timeline="props.timeline" :unit="props.unit" :era-of="props.eraOf" @save="(sp) => setSpan(f, sp)" />
                <button type="button" class="chip-x" :aria-label="`Remove ${r.label}: ${f.value}`" @click="run(() => deleteFact(props.world, f.id))">×</button>
              </span>
            </div>
          </td>
          <template v-if="!r.several">
            <td>
              <select class="standing" :class="r.facts[0]!.standing" :value="r.facts[0]!.standing" aria-label="Standing" @change="set(r.facts[0]!, { standing: ($event.target as HTMLSelectElement).value as Standing })">
                <option v-for="s in STANDINGS" :key="s" :value="s">{{ s }}</option>
              </select>
            </td>
            <td><button type="button" class="icon-btn small" :aria-label="`Remove ${r.label}`" @click="run(() => deleteFact(props.world, r.facts[0]!.id))">×</button></td>
          </template>
        </tr>
      </tbody>
    </table>
    <p v-if="prompt" class="small label-prompt" data-testid="label-prompt" aria-live="polite">
      <template v-if="!prompt.expected">
        {{ prompt.count }} {{ kindPlural }} have "{{ prompt.label }}" now ·
        <button type="button" class="linkish" tabindex="-1" @mousedown.prevent @click="expectIt">Expect it on every {{ props.entity.kind }}?</button> ·
        <button type="button" class="linkish muted" tabindex="-1" @mousedown.prevent @click="prompt = null">Not now</button>
      </template>
      <template v-else>
        “{{ prompt.label }}” is expected on every {{ props.entity.kind }} now ·
        <RouterLink :to="{ name: 'labels', params: { world: props.world } }">Labels</RouterLink>
      </template>
    </p>
    <p v-if="offer.length" class="small muted add-line" data-testid="add-line">
      Add:
      <template v-for="(l, i) in offer" :key="l"><span v-if="i"> · </span><button type="button" class="linkish" @click="start(l)">{{ l }}</button></template>
    </p>
    <form class="actions fact-add" @submit.prevent="add">
      <input ref="labelBox" v-model="label" class="filter" list="fact-labels" placeholder="Label (e.g. eye colour)" aria-label="New fact label" maxlength="100" />
      <datalist id="fact-labels"><option v-for="s in unused" :key="s" :value="s" /></datalist>
      <input ref="valueBox" v-model="value" class="filter grow" :list="listFor(label)" placeholder="Value" aria-label="New fact value" maxlength="5000" />
      <select v-model="newStanding" class="filter" aria-label="New fact standing" title="Planned until it is in the book; one click to canon">
        <option v-for="s in STANDINGS" :key="s" :value="s">{{ s }}</option>
      </select>
      <button class="btn btn-sm" type="submit" :disabled="!label.trim()">Add</button>
    </form>
    <datalist v-for="[l, id] in valueLists" :id="id" :key="id" :data-label="l">
      <option v-for="v in valuesOf(l)" :key="v.value" :value="v.value">{{ v.count ? `${v.value} (${v.count})` : v.value }}</option>
    </datalist>
  </section>
</template>
