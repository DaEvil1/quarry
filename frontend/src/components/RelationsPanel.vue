<script setup lang="ts">
import { computed, ref } from "vue";

import { addRelationship, deleteRelationship, typeOptions, updateRelationship } from "../bible";
import type { Entity, EntityRef, RelationType, Relationship, Standing } from "../types";
import EntityPicker from "./EntityPicker.vue";

// An entry's relationships, grouped by how they read from this entry, and adding one: pick who or what, then how.
const props = defineProps<{
  world: string;
  entity: Entity;
  relationships: Relationship[];
  types: RelationType[];
  names: EntityRef[];
}>();
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
const options = computed(() => (target.value ? typeOptions(props.types, props.entity.kind, target.value.kind) : []));
const STANDINGS: Standing[] = ["canon", "planned", "rumour"];

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
    type_id: typeId,
    a_id: forward === "true" ? props.entity.id : t.id,
    b_id: forward === "true" ? t.id : props.entity.id,
    standing: standing.value,
    note: note.value || null,
  };
  target.value = null;
  note.value = "";
  standing.value = "canon";
  void run(() => addRelationship(props.world, body));
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
          <span v-for="r in list" :key="r.id" class="rel" :class="`k-${r.other?.kind}`">
            <RouterLink class="kname" :to="{ name: 'entity', params: { world: props.world, id: r.other?.id } }">{{ r.other?.name }}</RouterLink>
            <select class="standing" :class="r.standing" :value="r.standing" aria-label="Standing" @change="run(() => updateRelationship(props.world, r, { standing: ($event.target as HTMLSelectElement).value as Standing }))">
              <option v-for="s in STANDINGS" :key="s" :value="s">{{ s }}</option>
            </select>
            <span v-if="r.note" class="muted small">— {{ r.note }}</span>
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
        <select v-model="standing" class="filter" aria-label="Standing">
          <option v-for="s in STANDINGS" :key="s" :value="s">{{ s }}</option>
        </select>
        <input v-model="note" class="filter grow" placeholder="Note (optional)" aria-label="Note" maxlength="5000" />
        <button class="btn btn-sm btn-primary" type="submit" :disabled="!choice">Add</button>
        <button class="btn btn-sm" type="button" @click="target = null">Cancel</button>
      </form>
    </div>
  </section>
</template>
