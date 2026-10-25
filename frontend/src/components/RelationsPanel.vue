<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { addRelationship, changeRole, deleteRelationship, roleSuggestions, rolesFor, typeOptions, updateRelationship, type RoleSuggestions } from "../bible";
import type { Entity, EntityRef, RelationType, Relationship, Span, Standing, StoryChapter } from "../types";
import { holds, type At, type IndexOf } from "../world/time";
import type { Unit } from "../world/when";
import EntityPicker from "./EntityPicker.vue";
import InlineText from "./InlineText.vue";
import SpanPicker from "./SpanPicker.vue";

// An entry's relationships, grouped by how they read from this entry, and adding one: pick who or what, then how. A
// type with a role ("member of") carries the holder's role in the group, with the roles used on it offered
// (docs/SPEC.md §13.4); a promotion is a new span, from a chosen chapter.
const props = defineProps<{
  world: string;
  entity: Entity;
  relationships: Relationship[];
  types: RelationType[];
  names: EntityRef[];
  timeline: StoryChapter[];
  asOf: At | null;
  indexOf: IndexOf;
  unit?: Unit;
}>();
const off = (r: Relationship) => props.asOf !== null && !holds(r, props.asOf, props.indexOf);
const setSpan = (r: Relationship, span: Span) => run(() => updateRelationship(props.world, r, span));
const emit = defineEmits<{ changed: []; error: [message: string] }>();

const groups = computed(() => {
  const out = new Map<string, Relationship[]>();
  for (const r of props.relationships) out.set(r.reads ?? r.label, [...(out.get(r.reads ?? r.label) ?? []), r]);
  return [...out.entries()].sort((a, b) => a[0].localeCompare(b[0]));
});

const target = ref<EntityRef | null>(null);
const choice = ref("");
const standing = ref<Standing>("canon");
const note = ref("");
const role = ref("");
const options = computed(() => (target.value ? typeOptions(props.types, props.entity.kind, target.value.kind) : []));
const STANDINGS: Standing[] = ["canon", "planned", "rumour"];
const chosenType = computed(() => props.types.find((t) => t.id === choice.value.split("|")[0]));
// the group a new relationship's role is in: the B side
const chosenGroup = computed(() => (choice.value.split("|")[1] === "true" ? target.value?.id : props.entity.id) ?? "");

// the roles used on each type, for the role field
const suggestions = ref<RoleSuggestions>({});
watch(
  () => [props.world, props.relationships],
  async () => {
    if (props.relationships.some((r) => r.has_role) || props.types.some((t) => t.has_role)) suggestions.value = await roleSuggestions(props.world).catch(() => suggestions.value);
  },
  { immediate: true },
);
const listId = (typeId: string, groupId: string) => `roles-${typeId}-${groupId}`;
const roleLists = computed(() => {
  const out = new Map<string, { role: string; count: number }[]>();
  const add = (typeId: string, groupId: string) => out.set(listId(typeId, groupId), rolesFor(suggestions.value, typeId, groupId));
  for (const r of props.relationships) if (r.has_role) add(r.type_id, r.b.id);
  if (chosenType.value?.has_role) add(chosenType.value.id, chosenGroup.value);
  return out;
});

function pick(e: EntityRef) {
  target.value = e;
  choice.value = options.value[0] ? `${options.value[0].type.id}|${options.value[0].forward}` : "";
}

async function run(fn: () => Promise<unknown>) {
  try {
    await fn();
    emit("changed");
  } catch (e) {
    emit("error", (e as Error).message);
  }
}

function add() {
  const t = target.value;
  if (!t || !choice.value) return;
  const [typeId, forward] = choice.value.split("|");
  const body = {
    type_id: typeId!,
    a_id: forward === "true" ? props.entity.id : t.id,
    b_id: forward === "true" ? t.id : props.entity.id,
    standing: standing.value,
    note: note.value || null,
    role: chosenType.value?.has_role ? role.value.trim() || null : null,
  };
  target.value = null;
  note.value = role.value = "";
  standing.value = "canon";
  void run(() => addRelationship(props.world, body));
}

// a promotion: end this span just before a chapter, and start a copy with the new role there
const changing = ref<string | null>(null);
const changeFrom = ref("");
const changeTo = ref("");
const changeTime = ref("");
function startChange(r: Relationship) {
  changing.value = r.id;
  changeFrom.value = props.timeline.find((c) => props.asOf !== null && props.indexOf(c.id) === props.asOf)?.id ?? "";
  changeTo.value = changeTime.value = "";
}
function doChange(r: Relationship) {
  if (!changeFrom.value) return;
  const to = changeTo.value.trim() || null;
  const at = changeFrom.value === "time" ? Number(changeTime.value.replace("−", "-")) : null;
  if (at !== null && !Number.isFinite(at)) return;
  changing.value = null;
  void run(() => changeRole(props.world, r, to, at === null ? { chapter: changeFrom.value } : { time: at }));
}
</script>

<template>
  <section class="card" data-testid="relationships">
    <div class="card-head">
      <h2>Relationships</h2>
      <RouterLink class="small" :to="{ name: 'relation-types', params: { world: props.world } }">Kinds of relationship</RouterLink>
    </div>
    <dl v-if="groups.length" class="relations">
      <template v-for="[reads, list] in groups" :key="reads">
        <dt>{{ reads }}</dt>
        <dd>
          <span v-for="r in list" :key="r.id" class="rel" :class="[`k-${r.other?.kind}`, { off: off(r) }]" :title="off(r) ? 'Not true at this point in the story' : ''" data-testid="relationship">
            <RouterLink class="kname" :to="{ name: 'entity', params: { world: props.world, id: r.other?.id } }">{{ r.other?.name }}</RouterLink>
            <span v-if="r.role || r.has_role" class="rel-role" data-testid="role">
              ·
              <InlineText :value="r.role ?? ''" label="Role" placeholder="+ role" :maxlength="100" :list="r.has_role ? listId(r.type_id, r.b.id) : undefined" @save="(v) => run(() => updateRelationship(props.world, r, { role: v || null }))" />
            </span>
            <select class="standing" :class="r.standing" :value="r.standing" aria-label="Standing" @change="run(() => updateRelationship(props.world, r, { standing: ($event.target as HTMLSelectElement).value as Standing }))">
              <option v-for="s in STANDINGS" :key="s" :value="s">{{ s }}</option>
            </select>
            <SpanPicker :span="r" :timeline="props.timeline" :unit="props.unit" @save="(sp) => setSpan(r, sp)" />
            <span v-if="r.note" class="muted small">— {{ r.note }}</span>
            <button v-if="r.has_role && props.timeline.length && changing !== r.id" type="button" class="linkish small" data-testid="change-role" @click="startChange(r)">Change role from here…</button>
            <form v-if="changing === r.id" class="span-form" data-testid="change-role-form" @submit.prevent="doChange(r)" @keydown.esc.prevent="changing = null">
              <label class="small muted">from
                <select v-model="changeFrom" class="filter" aria-label="New role from">
                  <option value="" disabled>a chapter…</option>
                  <option v-for="c in props.timeline" :key="c.id" :value="c.id">{{ c.title }}</option>
                  <option value="time">A time…</option>
                </select>
              </label>
              <input v-if="changeFrom === 'time'" v-model="changeTime" class="filter time-num" inputmode="decimal" aria-label="New role from a time" :placeholder="props.unit?.unit ?? 'year'" />
              <input v-model="changeTo" class="filter" :list="listId(r.type_id, r.b.id)" placeholder="new role" aria-label="New role" maxlength="100" />
              <button class="btn btn-sm btn-primary" type="submit" :disabled="!changeFrom">Change</button>
              <button class="btn btn-sm" type="button" @click="changing = null">Cancel</button>
            </form>
            <RouterLink class="small read-together" :to="{ name: 'entity-read', params: { world: props.world, id: props.entity.id }, query: { with: r.other?.id } }"
              :title="`Read the paragraphs that name both ${props.entity.name} and ${r.other?.name}`">Read together</RouterLink>
            <button type="button" class="icon-btn small" :aria-label="`Remove ${reads} ${r.other?.name}`" @click="run(() => deleteRelationship(props.world, r.id))">×</button>
          </span>
        </dd>
      </template>
    </dl>
    <p v-else class="empty">Nothing recorded yet.</p>

    <div class="rel-add">
      <EntityPicker
        v-if="!target"
        :entities="props.names"
        :exclude="[props.entity.id]"
        :placeholder="`Connect ${props.entity.name} to…`"
        @pick="pick"
        @cancel="target = null"
      />
      <form v-else class="actions" @submit.prevent="add">
        <span>{{ props.entity.name }}</span>
        <select v-model="choice" class="filter" aria-label="How they're connected">
          <option v-for="o in options" :key="`${o.type.id}|${o.forward}`" :value="`${o.type.id}|${o.forward}`">{{ o.reads }}</option>
        </select>
        <span class="kname" :class="`k-${target.kind}`">{{ target.name }}</span>
        <input v-if="chosenType?.has_role" v-model="role" class="filter" :list="listId(chosenType.id, chosenGroup)" placeholder="Role (optional)" aria-label="Role" maxlength="100" />
        <select v-model="standing" class="filter" aria-label="Standing">
          <option v-for="s in STANDINGS" :key="s" :value="s">{{ s }}</option>
        </select>
        <input v-model="note" class="filter grow" placeholder="Note (optional)" aria-label="Note" maxlength="5000" />
        <button class="btn btn-sm btn-primary" type="submit" :disabled="!choice">Add</button>
        <button class="btn btn-sm" type="button" @click="target = null">Cancel</button>
      </form>
    </div>
    <datalist v-for="[id, roles] in roleLists" :id="id" :key="id" data-testid="role-list">
      <option v-for="x in roles" :key="x.role" :value="x.role">{{ x.role }} ({{ x.count }})</option>
    </datalist>
  </section>
</template>
