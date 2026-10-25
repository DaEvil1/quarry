<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { chapterTies, type Choice, type Tie } from "../manuscript";

// The review before chapters leave the book (docs/SPEC.md §13.6.2): everything tied to them, grouped, each row with
// the choices that apply (keep, move to another chapter, mark as planned, drop) and the one it starts on, per row or
// for a whole group at once; then one line of harvest note per chapter, each skippable. Nothing changes until
// `done` is sent, with the choices; the page applies them in one go, with Undo.
const props = withDefaults(defineProps<{
  world: string;
  /** the chapters leaving */
  chapters: { id: string; title: string }[];
  /** accepting an experiment: its drafts are the likely places to move to */
  experiment?: string;
  /** where "move" can point: the chapters staying, and an experiment's drafts */
  targets: { id: string; title: string }[];
  verb: string;
  /** ask for harvest notes (not when reviewing a chapter already in Salvage) */
  notes?: boolean;
}>(), { notes: true, experiment: undefined });
const emit = defineEmits<{ done: [review: Choice[], notes: Record<string, string>]; cancel: [] }>();

const rows = ref<Tie[]>([]);
const loaded = ref(false);
const error = ref("");
const action = ref<Record<string, Tie["default"]>>({});
const to = ref<Record<string, string>>({});
const notes = ref<Record<string, string>>({});
onMounted(async () => {
  try {
    rows.value = props.chapters.length ? (await chapterTies(props.world, props.chapters.map((c) => c.id), props.experiment)).rows : [];
    for (const r of rows.value) {
      action.value[r.key] = r.default;
      to.value[r.key] = r.move_to?.id ?? "";
    }
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loaded.value = true;
  }
});

const KIND: Record<Tie["kind"], string> = {
  fact: "Facts",
  relationship: "Relationships",
  presence: "“Is at”",
  link: "Items",
  note: "The note for next time",
  event: "Events that happen in it",
  telling: "Tellings",
};
const FIELD: Record<string, string> = { from: "from", until: "until", established: "established in", is_at: "in", item: "linked to", note: "left in" };
const ACTION: Record<Tie["default"], string> = { keep: "keep", move: "move to…", planned: "mark as planned", drop: "drop" };
const ALL: Record<Tie["default"], string> = { keep: "keep all", move: "move all", planned: "mark all planned", drop: "drop all" };
const groups = computed(() => {
  const out: { kind: Tie["kind"]; rows: Tie[] }[] = [];
  for (const r of rows.value) {
    const g = out.find((x) => x.kind === r.kind);
    if (g) g.rows.push(r);
    else out.push({ kind: r.kind, rows: [r] });
  }
  return out;
});
function all(g: { rows: Tie[] }, a: Tie["default"]) {
  for (const r of g.rows) if (r.choices.includes(a)) action.value[r.key] = a;
}
const missingTarget = computed(() => rows.value.some((r) => action.value[r.key] === "move" && !to.value[r.key]));
function confirm() {
  if (missingTarget.value) return;
  const review: Choice[] = rows.value.map((r) => ({ key: r.key, action: action.value[r.key] ?? r.default, to: action.value[r.key] === "move" ? to.value[r.key] || null : null }));
  const kept: Record<string, string> = {};
  for (const [k, v] of Object.entries(notes.value)) if (v.trim()) kept[k] = v.trim();
  emit("done", review, kept);
}
</script>

<template>
  <section class="card review" data-testid="retire-review" @keydown.esc.prevent="emit('cancel')">
    <div class="card-head">
      <h2 v-if="!props.chapters.length">Nothing leaves the book</h2>
      <h2 v-else>Before {{ props.chapters.length === 1 ? `“${props.chapters[0]!.title}” leaves` : `${props.chapters.length} chapters leave` }} the book</h2>
    </div>
    <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
    <p v-if="loaded && !rows.length" class="muted small" data-testid="review-empty">Nothing is tied to {{ props.chapters.length === 1 ? "it" : "them" }}.</p>
    <p v-else-if="loaded" class="muted small">Everything tied to {{ props.chapters.length === 1 ? "it" : "them" }}. Nothing changes until you {{ props.verb.toLowerCase() }}.</p>
    <section v-for="g in groups" :key="g.kind" class="review-group" :data-testid="`review-${g.kind}`">
      <h3 class="small muted">
        {{ KIND[g.kind] }} ({{ g.rows.length }})
        <span class="qrow">
          <button v-for="a in ['keep', 'move', 'planned', 'drop'] as const" v-show="g.rows.some((r) => r.choices.includes(a))" :key="a" type="button" class="qchip quiet" @click="all(g, a)">{{ ALL[a] }}</button>
        </span>
      </h3>
      <div v-for="r in g.rows" :key="r.key" class="review-row" :data-key="r.key" data-testid="review-row">
        <div class="grow">
          <span>{{ r.text }}</span>
          <span class="muted small"> · {{ FIELD[r.field] ?? r.field }} “{{ r.chapter.title }}”</span>
          <div v-if="r.evidence" class="small muted evidence">“{{ r.evidence }}”</div>
          <div v-if="action[r.key] === 'keep' && r.keep_text" class="small" data-testid="keep-text">{{ r.keep_text }}</div>
          <div v-if="r.warn" class="small warn" data-testid="review-warn">{{ r.warn }}: keeping it would take them in too</div>
        </div>
        <select v-model="action[r.key]" class="filter" :aria-label="`What happens to ${r.text}`" data-testid="review-action">
          <option v-for="a in r.choices" :key="a" :value="a">{{ ACTION[a] }}</option>
        </select>
        <select v-if="action[r.key] === 'move'" v-model="to[r.key]" class="filter" :aria-label="`Move ${r.text} to`" data-testid="review-to">
          <option value="" disabled>a chapter…</option>
          <option v-for="t in props.targets" :key="t.id" :value="t.id">{{ t.title }}</option>
        </select>
      </div>
    </section>
    <div v-if="props.notes !== false && loaded && props.chapters.length" class="review-notes">
      <h3 class="small muted">What was alive in {{ props.chapters.length === 1 ? "it" : "them" }}? (each optional)</h3>
      <label v-for="c in props.chapters" :key="c.id" class="field">
        <span class="small">{{ c.title }}</span>
        <input v-model="notes[c.id]" class="filter" maxlength="5000" :aria-label="`Harvest note for ${c.title}`" placeholder="a harvest note" />
      </label>
    </div>
    <div class="actions">
      <button type="button" class="btn btn-primary" :disabled="!loaded || missingTarget" data-testid="review-confirm" @click="confirm">{{ props.verb }}</button>
      <button type="button" class="btn" @click="emit('cancel')">Cancel</button>
    </div>
  </section>
</template>
