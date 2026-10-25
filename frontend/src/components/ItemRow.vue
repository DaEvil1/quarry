<script setup lang="ts">
import { computed, nextTick, ref } from "vue";

import { entityNames, linkItem, unlinkItem } from "../bible";
import { age, closeItem, ItemConflict, reopenItem, undoClose, updateItem } from "../items";
import { CAPTURE_KINDS, STATUS_LABELS, firstLine, type CloseStatus, type EntityRef, type Item, type World } from "../types";
import EntityPicker from "./EntityPicker.vue";
import FollowsNote from "./FollowsNote.vue";
import MentionText from "./MentionText.vue";
import ItemOrigin from "./ItemOrigin.vue";

const props = defineProps<{ item: Item; world: World; open: boolean }>();
const emit = defineEmits<{
  toggle: [];
  /** the item changed but stays where it is */
  changed: [item: Item];
  /** the item left this list (closed, deferred or reopened); `undo` puts it back (with the rows made in the
   * follow-up step of the decision it logged, if any); `decision`: the decision its close logged */
  moved: [item: Item, label: string, undo: (made?: string[]) => Promise<void>, decision?: { id: string; text: string }];
  /** something else changed it (a name fix, a tag): load it again */
  refresh: [];
}>();

const isOpenTask = computed(() => props.item.kind === "task" && (props.item.status === "open" || props.item.status === "deferred"));
const projectName = computed(() =>
  props.item.project ? (props.world.projects.find((p) => p.slug === props.item.project)?.name ?? props.item.project) : null,
);
const decision = ref("");
const editing = ref(false);
const draft = ref("");
const draftKind = ref(props.item.kind);
const busy = ref(false);
const error = ref("");

async function run(fn: () => Promise<void>) {
  busy.value = true;
  error.value = "";
  try {
    await fn();
  } catch (e) {
    if (e instanceof ItemConflict) {
      emit("changed", e.current);
      editing.value = false;
    }
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}

const close = (status: CloseStatus) =>
  run(async () => {
    const text = decision.value.trim();
    const out = await closeItem(props.world.slug, props.item.id, status, status === "deferred" ? {} : { decision: text });
    decision.value = "";
    emit("moved", out.item, `${STATUS_LABELS[status]}${out.decision_id ? " · decision logged" : ""}`,
      (made?: string[]) => undoClose(props.world.slug, props.item.id, out.decision_id, made),
      out.decision_id ? { id: out.decision_id, text } : undefined);
  });

const reopen = () =>
  run(async () => {
    const before = props.item.status;
    const item = await reopenItem(props.world.slug, props.item.id);
    emit("moved", item, "Reopened", async () => {
      await closeItem(props.world.slug, props.item.id, before as CloseStatus);
    });
  });

function startEdit() {
  draft.value = props.item.body;
  draftKind.value = props.item.kind;
  editing.value = true;
}

const saveEdit = () =>
  run(async () => {
    const item = await updateItem(props.world.slug, props.item, { body: draft.value, kind: draftKind.value });
    editing.value = false;
    emit("changed", item);
  });

// tags: bible entries the item is about
const tagging = ref(false);
const names = ref<EntityRef[]>([]);
const picker = ref<InstanceType<typeof EntityPicker> | null>(null);

async function startTag() {
  // the names first: a picker that opens empty swallows a quick "type and Enter"
  names.value = await entityNames(props.world.slug);
  tagging.value = true;
  await nextTick();
  picker.value?.focus();
}

const tag = (e: EntityRef) =>
  run(async () => {
    await linkItem(props.world.slug, props.item.id, e.id);
    tagging.value = false;
    emit("refresh");
  });

const untag = (e: EntityRef) =>
  run(async () => {
    await unlinkItem(props.world.slug, props.item.id, e.id);
    emit("refresh");
  });

const move = (project: string) =>
  run(async () => {
    emit("changed", await updateItem(props.world.slug, props.item, { project: project || null }));
  });
</script>

<template>
  <li class="item" :class="{ open: props.open }">
    <button type="button" class="item-head" :aria-expanded="props.open" @click="emit('toggle')">
      <span class="pill" :class="`kind-${props.item.kind}`">{{ props.item.kind }}</span>
      <!-- open, the full text shows below instead -->
      <span class="item-line">{{ props.open ? "" : firstLine(props.item) }}</span>
      <span v-if="projectName" class="pill">{{ projectName }}</span>
      <span class="muted small item-age">{{ age(props.item.created_at) }}</span>
    </button>
    <div v-if="props.open" class="item-body">
      <template v-if="editing">
        <label :for="`edit-${props.item.id}`" class="visually-hidden">Text</label>
        <textarea :id="`edit-${props.item.id}`" v-model="draft" class="capture-box" rows="5" />
        <div class="actions">
          <select v-model="draftKind" aria-label="Kind">
            <option v-for="k in CAPTURE_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
          <button type="button" class="btn btn-sm btn-primary" :disabled="busy" @click="saveEdit">Save</button>
          <button type="button" class="btn btn-sm" @click="editing = false">Cancel</button>
        </div>
      </template>
      <template v-else>
        <p class="item-text">
          <MentionText
            :text="props.item.body"
            :mentions="props.item.mentions"
            :world="props.world.slug"
            :source="{ table: 'item', id: props.item.id }"
            @fixed="emit('refresh')"
          />
        </p>
        <div class="chips">
          <span v-for="e in props.item.entities" :key="e.id" class="chip static tag">
            <RouterLink :to="{ name: 'entity', params: { world: props.world.slug, id: e.id } }">{{ e.name }}</RouterLink>
            <button type="button" class="chip-x" :aria-label="`Untag ${e.name}`" @click="untag(e)">×</button>
          </span>
          <button v-if="!tagging" type="button" class="chip" @click="startTag">+ Tag</button>
        </div>
        <EntityPicker
          v-if="tagging"
          ref="picker"
          :entities="names"
          :exclude="props.item.entities.map((e) => e.id)"
          @pick="tag"
          @cancel="tagging = false"
        />
        <p v-if="props.item.closed_note" class="muted small">Note: {{ props.item.closed_note }}</p>
        <ItemOrigin v-if="props.item.origin" :world="props.world.slug" :origin="props.item.origin" />
        <p v-if="props.item.follows?.length || isOpenTask" class="small"><FollowsNote :world="props.world.slug" :follows="props.item.follows" :row="isOpenTask ? { table: 'item', id: props.item.id, entities: props.item.entities.map((e) => e.id) } : null" task @changed="emit('refresh')" /></p>
        <p class="muted small">
          {{ STATUS_LABELS[props.item.status] }}
          <template v-if="props.item.source"> · from {{ props.item.source }}</template>
        </p>
      </template>

      <template v-if="!editing && props.item.status !== 'accepted' && props.item.status !== 'rejected' && props.item.status !== 'harvested'">
        <div class="field">
          <label :for="`decision-${props.item.id}`" class="small muted">Decision (optional, for accept or reject)</label>
          <input :id="`decision-${props.item.id}`" v-model="decision" type="text" maxlength="1000" />
        </div>
        <div class="actions">
          <button type="button" class="btn btn-sm btn-primary" :disabled="busy" @click="close('accepted')">Accept</button>
          <button type="button" class="btn btn-sm" :disabled="busy" @click="close('rejected')">Reject</button>
          <button type="button" class="btn btn-sm" :disabled="busy" @click="close('harvested')">Harvest</button>
          <button
            v-if="props.item.status !== 'deferred'"
            type="button"
            class="btn btn-sm"
            :disabled="busy"
            @click="close('deferred')"
          >
            Defer
          </button>
        </div>
      </template>
      <div v-if="!editing" class="actions">
        <button v-if="props.item.status !== 'open'" type="button" class="btn btn-sm" :disabled="busy" @click="reopen">
          Reopen
        </button>
        <button type="button" class="linkish small" @click="startEdit">Edit</button>
        <label :for="`move-${props.item.id}`" class="visually-hidden">Move to</label>
        <select
          :id="`move-${props.item.id}`"
          class="filter"
          :value="props.item.project ?? ''"
          @change="move(($event.target as HTMLSelectElement).value)"
        >
          <option value="">Whole world</option>
          <option v-for="p in props.world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
      </div>
      <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
    </div>
  </li>
</template>
