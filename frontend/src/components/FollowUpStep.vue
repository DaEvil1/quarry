<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";

import { del } from "../api";
import { factSuggestions, typeOptions, type KindSuggestions } from "../bible";
import {
  addFollowup,
  candidates as loadCandidates,
  decisionOffers,
  detachFollowup,
  followupToast,
  type Added,
  type Candidate,
  type FollowupCounts,
  type NamedChapter,
  type Offers,
} from "../followups";
import type { EntityRef, Span, Standing } from "../types";
import { kindsOf, useCards } from "../world/cards";
import { norm } from "../world/time";
import EntityPicker from "./EntityPicker.vue";
import SpanPicker from "./SpanPicker.vue";

// The follow-up step (docs/SPEC.md §16.3): one row under a decision's line, keyboard first. f a planned fact, w a
// relationship (with), t a task, x attach an existing row; Enter or Esc on the row ends the step. In a form Enter saves
// and the row comes back as "+ another", Esc goes back to the row without saving. On the phone the keys are chips. What
// the forms offer (the decision's entries, a chapter it names) is worked out once, when the step opens.
const props = defineProps<{
  world: string;
  decision: { id: string; text: string };
  /** the words before the row: "Decision logged" after a close */
  lead?: string;
  /** take the keyboard when it opens (after a close, or `+ follow-up`) */
  autofocus?: boolean;
}>();
const emit = defineEmits<{ added: [added: Added]; counts: [counts: FollowupCounts | null]; done: [] }>();

const cards = useCards();
type Mode = "choose" | "fact" | "relationship" | "task" | "attach";
const mode = ref<Mode>("choose");
const another = ref(false);
const busy = ref(false);
const error = ref("");
const root = ref<HTMLElement | null>(null);
const offers = ref<Offers>({ chapters: [], entities: [] });

// what the decision offers, asked for once when the step opens; a form opened before it arrives waits for it
const ready = decisionOffers(props.world, props.decision.id)
  .then((o) => (offers.value = o))
  .catch(() => {
    /* the forms work without what the decision offers */
  });
onMounted(() => {
  if (props.autofocus) root.value?.focus();
});

const entityChips = ref<EntityRef[]>([]);
const tagged = computed(() => offers.value.entities.filter((e) => e.tagged));
function chipsFor(): EntityRef[] {
  return offers.value.entities.map(({ id, name, kind }) => ({ id, name, kind }));
}

async function open(m: Mode) {
  error.value = "";
  await ready;
  mode.value = m;
  entityChips.value = chipsFor();
  if (m === "fact") startFact();
  if (m === "relationship") startRelationship();
  if (m === "task") startTask();
  if (m === "attach") await startAttach();
  await nextTick();
  (root.value?.querySelector("[data-first]") as HTMLElement | null)?.focus();
}

function back() {
  mode.value = "choose";
  error.value = "";
  void nextTick(() => root.value?.focus());
}

function finish() {
  emit("done");
}

function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (mode.value !== "choose") {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      back();
    }
    return;
  }
  if ((e.target as HTMLElement | null)?.tagName === "BUTTON" && e.key === "Enter") return;
  const keys: Record<string, () => unknown> = {
    f: () => open("fact"),
    w: () => open("relationship"),
    t: () => open("task"),
    x: () => open("attach"),
    Enter: finish,
    Escape: finish,
  };
  const fn = keys[e.key];
  if (fn) {
    e.preventDefault();
    e.stopPropagation();
    void fn();
  }
}

async function save(body: Record<string, unknown>, label: (a: Added) => string) {
  busy.value = true;
  error.value = "";
  try {
    const out = await addFollowup(props.world, props.decision.id, body);
    emit("added", out);
    emit("counts", out.counts);
    followupToast.value = {
      label: label(out),
      undo: async () => {
        const r = await detachFollowup(props.world, props.decision.id, out.followup.id);
        if (out.made) await del(`/api/worlds/${encodeURIComponent(props.world)}/${out.made.table === "fact" ? "facts" : out.made.table === "relationship" ? "relationships" : "items"}/${out.made.id}`);
        emit("counts", r.counts);
      },
    };
    another.value = true;
    back();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}

// ---- a chapter the decision names, offered for a span: one click uses it ----
const span = ref<Span>({ from_chapter_id: null, until_chapter_id: null });
const offerSpan = (c: NamedChapter, side: "from" | "until") => {
  span.value = { ...span.value, [`${side}_chapter_id`]: c.id, [`${side}_time`]: null, outside_time: false } as Span;
};

// ---- planned fact ----
const factEntity = ref<string | null>(null);
const label = ref("");
const value = ref("");
const standing = ref<Standing>("planned");
const otherPicker = ref<"fact" | "a" | "b" | null>(null);
const suggestions = ref<Record<string, KindSuggestions>>({});
function startFact() {
  factEntity.value = tagged.value[0]?.id ?? entityChips.value[0]?.id ?? null;
  label.value = value.value = "";
  standing.value = "planned";
  span.value = { from_chapter_id: null, until_chapter_id: null };
  if (!Object.keys(suggestions.value).length) void factSuggestions(props.world).then((s) => (suggestions.value = s)).catch(() => {});
}
const factKind = computed(() => cards.byId.get(factEntity.value ?? "")?.kind ?? entityChips.value.find((e) => e.id === factEntity.value)?.kind ?? "character");
const labelList = computed(() => suggestions.value[factKind.value]?.labels ?? []);
const valueList = computed(() => suggestions.value[factKind.value]?.values[norm(label.value)] ?? []);
function pickOther(e: EntityRef) {
  if (!entityChips.value.some((x) => x.id === e.id)) entityChips.value = [...entityChips.value, e];
  if (otherPicker.value === "fact") factEntity.value = e.id;
  if (otherPicker.value === "a") relA.value = e.id;
  if (otherPicker.value === "b") relB.value = e.id;
  otherPicker.value = null;
}
function saveFact() {
  const e = entityChips.value.find((x) => x.id === factEntity.value);
  if (!e || !label.value.trim() || busy.value) return;
  const fact = { entity_id: e.id, label: label.value, value: value.value, standing: standing.value, ...span.value };
  void save({ fact }, () => `${standing.value === "canon" ? "Canon" : "Planned"} "${label.value.trim()}${value.value.trim() ? `: ${value.value.trim()}` : ""}" on ${e.name} · follows the decision`);
}

// ---- planned relationship ----
const relA = ref<string | null>(null);
const relB = ref<string | null>(null);
const relType = ref("");
const role = ref("");
function startRelationship() {
  const first = [...tagged.value, ...entityChips.value];
  relA.value = first[0]?.id ?? null;
  relB.value = first.find((e) => e.id !== relA.value)?.id ?? null;
  role.value = "";
  standing.value = "planned";
  span.value = { from_chapter_id: null, until_chapter_id: null };
  relType.value = "";
}
const kindsFor = (id: string | null) => {
  const c = id ? cards.byId.get(id) : undefined;
  return c ? kindsOf(c) : [entityChips.value.find((e) => e.id === id)?.kind ?? "character"];
};
const relOptions = computed(() => (relA.value && relB.value ? typeOptions(cards.types, kindsFor(relA.value), kindsFor(relB.value)) : []));
const relChoice = computed(() => relOptions.value.find((o) => `${o.type.id}|${o.forward}` === relType.value) ?? relOptions.value[0]);
function saveRelationship() {
  const o = relChoice.value;
  if (!o || !relA.value || !relB.value || relA.value === relB.value || busy.value) return;
  const [a, b] = o.forward ? [relA.value, relB.value] : [relB.value, relA.value];
  const name = (id: string) => entityChips.value.find((e) => e.id === id)?.name ?? "";
  const relationship = { type_id: o.type.id, a_id: a, b_id: b, standing: standing.value, ...(o.type.has_role && role.value.trim() ? { role: role.value } : {}), ...span.value };
  void save({ relationship }, () => `Planned "${name(relA.value!)} ${o.reads} ${name(relB.value!)}" · follows the decision`);
}

// ---- task ----
const taskText = ref("");
const taskEntities = ref<string[]>([]);
const taskChapters = ref<string[]>([]);
const moreChapter = ref("");
function startTask() {
  taskText.value = "";
  taskEntities.value = tagged.value.map((e) => e.id);
  taskChapters.value = [];
  moreChapter.value = "";
}
const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
const extraChapters = computed(() => taskChapters.value.filter((id) => !offers.value.chapters.some((c) => c.id === id)).map((id) => cards.timeline.find((c) => c.id === id)).filter((c) => !!c));
function addChapter() {
  if (moreChapter.value && !taskChapters.value.includes(moreChapter.value)) taskChapters.value = [...taskChapters.value, moreChapter.value];
  moreChapter.value = "";
}
function saveTask() {
  if (!taskText.value.trim() || busy.value) return;
  void save({ item: { body: taskText.value, entities: taskEntities.value, chapters: taskChapters.value } }, () => "Task added · follows the decision");
}

// ---- attach what exists ----
const pool = ref<Candidate[]>([]);
const q = ref("");
const active = ref(0);
async function startAttach() {
  q.value = "";
  active.value = 0;
  try {
    pool.value = await loadCandidates(props.world, props.decision.id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
const shown = computed(() => {
  const needle = q.value.trim().toLowerCase();
  return (needle ? pool.value.filter((c) => c.text.toLowerCase().includes(needle)) : pool.value).slice(0, 12);
});
function attach(c: Candidate | undefined) {
  if (!c || busy.value) return;
  void save({ attach: { table: c.table, id: c.id } }, () => `Attached · follows the decision`);
}
function attachKey(e: KeyboardEvent) {
  if (e.key === "ArrowDown") active.value = Math.min(active.value + 1, shown.value.length - 1);
  else if (e.key === "ArrowUp") active.value = Math.max(active.value - 1, 0);
  else if (e.key === "Enter") attach(shown.value[active.value]);
  else return;
  e.preventDefault();
}
</script>

<template>
  <div ref="root" class="fu-step" tabindex="-1" data-testid="followup-step" @keydown="onKey">
    <div v-if="mode === 'choose'" class="fu-choose small" data-testid="followup-row">
      <span v-if="props.lead && !another" class="muted">{{ props.lead }} ·</span>
      <span class="fu-plus-label">{{ another ? "+ another" : "+ follow-up" }}:</span>
      <button type="button" class="qchip" data-testid="fu-fact" @click="open('fact')"><kbd class="desk-only">f</kbd> fact</button>
      <button type="button" class="qchip" data-testid="fu-relationship" @click="open('relationship')"><kbd class="desk-only">w</kbd> relationship</button>
      <button type="button" class="qchip" data-testid="fu-task" @click="open('task')"><kbd class="desk-only">t</kbd> task</button>
      <button type="button" class="qchip" data-testid="fu-attach" @click="open('attach')"><kbd class="desk-only">x</kbd> attach existing</button>
      <button type="button" class="qchip quiet" data-testid="fu-skip" @click="finish"><kbd class="desk-only">Enter</kbd> {{ another ? "done" : "skip" }}</button>
    </div>

    <!-- a planned fact: the entry, label and value, when it holds, planned -->
    <form v-else-if="mode === 'fact'" class="fu-form" data-testid="fu-fact-form" @submit.prevent="saveFact">
      <div class="qrow">
        <span class="small muted">Fact on</span>
        <button v-for="e in entityChips" :key="e.id" type="button" class="qchip" :class="[`k-${e.kind}`, { on: factEntity === e.id }]" :aria-pressed="factEntity === e.id" @click="factEntity = e.id">{{ e.name }}</button>
        <button type="button" class="qchip quiet" @click="otherPicker = 'fact'">Other…</button>
      </div>
      <EntityPicker v-if="otherPicker === 'fact'" :entities="cards.names" placeholder="Another entry…" autofocus @pick="pickOther" @cancel="otherPicker = null" />
      <div class="actions">
        <input v-model="label" data-first class="filter" list="fu-labels" placeholder="Label (e.g. status)" aria-label="Follow-up fact label" maxlength="100" />
        <datalist id="fu-labels"><option v-for="s in labelList" :key="s" :value="s" /></datalist>
        <input v-model="value" class="filter grow" list="fu-values" placeholder="Value" aria-label="Follow-up fact value" maxlength="5000" />
        <datalist id="fu-values"><option v-for="v in valueList" :key="v.value" :value="v.value" /></datalist>
      </div>
      <div class="qrow small">
        <span class="muted">When it holds:</span>
        <SpanPicker :span="span" :timeline="cards.timeline" :unit="cards.unit" @save="(sp) => (span = sp)" />
      </div>
      <div v-for="c in offers.chapters" :key="c.id" class="qrow small fu-offer" data-testid="fu-offer">
        <span class="muted">Named in the decision: {{ c.label }} ·</span>
        <button type="button" class="linkish" @click="offerSpan(c, 'from')">From</button> ·
        <button type="button" class="linkish" @click="offerSpan(c, 'until')">Until</button>
      </div>
      <div class="actions">
        <span class="pill" :class="standing">{{ standing }}</span>
        <button type="button" class="linkish small" :title="standing === 'planned' ? 'Already in the book: the follow-up is done at once' : ''" @click="standing = standing === 'planned' ? 'canon' : 'planned'">{{ standing === "planned" ? "canon instead" : "planned instead" }}</button>
        <button class="btn btn-sm btn-primary" type="submit" :disabled="busy || !label.trim() || !factEntity">Save</button>
        <button class="btn btn-sm" type="button" @click="back">Cancel</button>
        <span class="muted small desk-only">Enter saves, Esc goes back</span>
      </div>
    </form>

    <!-- a planned relationship: A, the type, B, a role where it has one, when it holds -->
    <form v-else-if="mode === 'relationship'" class="fu-form" data-testid="fu-relationship-form" @submit.prevent="saveRelationship">
      <div class="qrow">
        <button v-for="e in entityChips" :key="e.id" type="button" class="qchip" :class="[`k-${e.kind}`, { on: relA === e.id }]" :aria-pressed="relA === e.id" :data-first="relA === e.id ? '' : undefined" @click="relA = e.id">{{ e.name }}</button>
        <button type="button" class="qchip quiet" @click="otherPicker = 'a'">Other…</button>
      </div>
      <EntityPicker v-if="otherPicker === 'a' || otherPicker === 'b'" :entities="cards.names" placeholder="Another entry…" autofocus @pick="pickOther" @cancel="otherPicker = null" />
      <div class="actions">
        <select v-model="relType" class="filter" aria-label="Follow-up relationship type">
          <option v-for="o in relOptions" :key="`${o.type.id}|${o.forward}`" :value="`${o.type.id}|${o.forward}`">{{ o.reads }}</option>
        </select>
        <input v-if="relChoice?.type.has_role" v-model="role" class="filter" placeholder="Role" aria-label="Role" maxlength="100" />
      </div>
      <div class="qrow">
        <button v-for="e in entityChips" :key="e.id" type="button" class="qchip" :class="[`k-${e.kind}`, { on: relB === e.id }]" :aria-pressed="relB === e.id" @click="relB = e.id">{{ e.name }}</button>
        <button type="button" class="qchip quiet" @click="otherPicker = 'b'">Other…</button>
      </div>
      <div class="qrow small">
        <span class="muted">When it holds:</span>
        <SpanPicker :span="span" :timeline="cards.timeline" :unit="cards.unit" @save="(sp) => (span = sp)" />
      </div>
      <div v-for="c in offers.chapters" :key="c.id" class="qrow small fu-offer">
        <span class="muted">Named in the decision: {{ c.label }} ·</span>
        <button type="button" class="linkish" @click="offerSpan(c, 'from')">From</button> ·
        <button type="button" class="linkish" @click="offerSpan(c, 'until')">Until</button>
      </div>
      <div class="actions">
        <span class="pill planned">planned</span>
        <button class="btn btn-sm btn-primary" type="submit" :disabled="busy || !relChoice || !relA || !relB || relA === relB">Save</button>
        <button class="btn btn-sm" type="button" @click="back">Cancel</button>
        <span class="muted small desk-only">Enter saves, Esc goes back</span>
      </div>
    </form>

    <!-- a task: your own line, the decision's entries ticked, a chapter it names offered unticked -->
    <form v-else-if="mode === 'task'" class="fu-form" data-testid="fu-task-form" @submit.prevent="saveTask">
      <input v-model="taskText" data-first class="filter grow" placeholder="The task" aria-label="Follow-up task" maxlength="20000" required />
      <div class="qrow">
        <button v-for="e in tagged" :key="e.id" type="button" class="qchip" :class="[`k-${e.kind}`, { on: taskEntities.includes(e.id) }]" :aria-pressed="taskEntities.includes(e.id)" @click="taskEntities = toggle(taskEntities, e.id)">{{ taskEntities.includes(e.id) ? "✓ " : "" }}{{ e.name }}</button>
        <button v-for="c in offers.chapters" :key="c.id" type="button" class="qchip" :class="{ on: taskChapters.includes(c.id) }" :aria-pressed="taskChapters.includes(c.id)" data-testid="fu-task-chapter" @click="taskChapters = toggle(taskChapters, c.id)">{{ taskChapters.includes(c.id) ? "✓ " : "" }}{{ c.label }} · named in the decision</button>
        <button v-for="c in extraChapters" :key="c!.id" type="button" class="qchip on" aria-pressed="true" @click="taskChapters = toggle(taskChapters, c!.id)">✓ {{ c!.title }}</button>
        <label class="visually-hidden" for="fu-chapter">Chapter…</label>
        <select id="fu-chapter" v-model="moreChapter" class="filter small" @change="addChapter">
          <option value="">Chapter…</option>
          <option v-for="c in cards.timeline" :key="c.id" :value="c.id">{{ c.title }}</option>
        </select>
      </div>
      <div class="actions">
        <button class="btn btn-sm btn-primary" type="submit" :disabled="busy || !taskText.trim()">Save</button>
        <button class="btn btn-sm" type="button" @click="back">Cancel</button>
        <span class="muted small desk-only">Enter saves, Esc goes back</span>
      </div>
    </form>

    <!-- attach a planned row or an open task that exists -->
    <div v-else class="fu-form" data-testid="fu-attach-form">
      <input v-model="q" data-first class="filter grow" placeholder="Planned facts and relationships, open tasks…" aria-label="Attach existing" @keydown="attachKey" @input="active = 0" />
      <ul class="fu-pool small" role="listbox">
        <li v-for="(c, i) in shown" :key="c.id" role="option" :aria-selected="i === active">
          <button type="button" class="linkish" @click="attach(c)">{{ c.text }}</button>
        </li>
        <li v-if="!shown.length" class="muted">Nothing planned or open to attach.</li>
      </ul>
      <button class="btn btn-sm" type="button" @click="back">Cancel</button>
    </div>

    <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
  </div>
</template>
