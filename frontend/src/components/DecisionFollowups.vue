<script setup lang="ts">
import { computed, ref, watch } from "vue";

import {
  addFollowup,
  detachFollowup,
  dropFollowup,
  followupTail,
  followupToast,
  listFollowups,
  pillText,
  undropFollowup,
  type DecisionLine,
  type Followup,
  type FollowupCounts,
} from "../followups";
import FollowUpStep from "./FollowUpStep.vue";

// On a decision's line, wherever it is (docs/SPEC.md §16.2, §16.3): the quiet pill worked out from its follow-ups
// ("1 of 2 to do", "done"; none for a settled decision), and "+ follow-up" (on hover or focus on the desk, always on
// the phone). The pill opens the follow-up list under the line, to do first, then done, then dropped; "+ follow-up"
// opens it with the follow-up step. Put it inside the line's own element: it adds a full-width block under it.
const props = defineProps<{
  world: string;
  decision: DecisionLine;
  /** open with the list showing (the Decisions filter "With open follow-ups") */
  open?: boolean;
  /** open with the step taking the keyboard (a decision just written) */
  step?: boolean;
}>();
const emit = defineEmits<{ counts: [counts: FollowupCounts | null] }>();

const counts = ref<FollowupCounts | null>(props.decision.followups ?? null);
watch(() => props.decision.followups, (c) => (counts.value = c ?? null));
const pill = computed(() => pillText(counts.value));
const showList = ref(false);
const stepOpen = ref(!!props.step);
const list = ref<Followup[]>([]);
const error = ref("");

async function load() {
  try {
    list.value = await listFollowups(props.world, props.decision.id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
if (props.open || props.step) {
  showList.value = !!props.open;
  if (props.open) void load();
}

function setCounts(c: FollowupCounts | null) {
  counts.value = c;
  emit("counts", c);
}

async function togglePill() {
  showList.value = !showList.value;
  if (showList.value) await load();
}
function plus() {
  stepOpen.value = true;
  showList.value = true;
  void load();
}
async function stepDone() {
  stepOpen.value = false;
  if (!list.value.length) showList.value = false;
}

async function drop(f: Followup) {
  const r = await dropFollowup(props.world, props.decision.id, f.id);
  setCounts(r.counts);
  await load();
  followupToast.value = {
    label: "Dropped · stays on the decision",
    undo: async () => {
      setCounts((await undropFollowup(props.world, props.decision.id, f.id)).counts);
      await load();
    },
  };
}
async function detach(f: Followup) {
  const r = await detachFollowup(props.world, props.decision.id, f.id);
  setCounts(r.counts);
  await load();
  followupToast.value = {
    label: "Detached",
    undo: r.attach
      ? async () => {
          setCounts((await addFollowup(props.world, props.decision.id, { attach: r.attach })).counts);
          await load();
        }
      : null,
  };
}

const STATE = { todo: "to do", done: "done", dropped: "dropped" } as const;
function linkOf(f: Followup) {
  if (f.link?.item) return { name: "item", params: { world: props.world, id: f.link.item } };
  if (f.link?.entity) return { name: "entity", params: { world: props.world, id: f.link.entity }, hash: `#${f.link.fact ? "fact" : "rel"}-${f.link.fact ?? f.link.relationship}` };
  return null;
}
defineExpose({ plus, reload: load });
</script>

<template>
  <button v-if="pill" type="button" class="fu-pill" :class="{ done: !counts?.todo }" :aria-expanded="showList" data-testid="fu-pill" @click="togglePill">
    <template v-if="!counts?.todo">✓ </template>{{ pill }}
  </button>
  <button type="button" class="linkish small fu-add" data-testid="fu-add" @click="plus">+ follow-up</button>
  <div v-if="showList || stepOpen" class="fu-under" data-testid="fu-under">
    <ul v-if="showList && list.length" class="fu-list small" data-testid="fu-list">
      <li v-for="f in list" :key="f.id" :class="f.state" data-testid="fu-line">
        <span class="fu-state">{{ STATE[f.state] }}</span>
        <RouterLink v-if="linkOf(f)" class="fu-text" :to="linkOf(f)!">{{ f.text }}</RouterLink>
        <span v-else class="fu-text">{{ f.text }}</span>
        <span class="muted">· {{ followupTail(f) }}</span>
        <RouterLink v-if="f.written" class="muted" :to="{ name: 'chapter', params: { world: props.world, id: f.written.id }, query: { panel: 'looseEnds' } }">· chapter {{ f.written.n }} is written</RouterLink>
        <template v-if="f.state === 'todo'">
          <button type="button" class="linkish small" @click="drop(f)">Drop</button>
          <button type="button" class="linkish small muted" @click="detach(f)">Detach</button>
        </template>
      </li>
    </ul>
    <FollowUpStep
      v-if="stepOpen"
      :world="props.world"
      :decision="props.decision"
      autofocus
      @added="load"
      @counts="setCounts"
      @done="stepDone"
    />
    <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
  </div>
</template>
