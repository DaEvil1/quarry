<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { addRelationType, deleteRelationType, relationTypes, updateRelationType } from "../bible";
import InlineText from "../components/InlineText.vue";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type RelationType } from "../types";
import NotFoundView from "./NotFoundView.vue";

// The world's vocabulary of relationships: what can join what, and how it reads from each side.
const route = useRoute();
const session = useSession();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const types = ref<RelationType[]>([]);
const error = ref("");

const KINDS = [{ value: "*", label: "Anything", plural: "Anything" }, ...ENTITY_KINDS];
const kindLabel = (k: string) => KINDS.find((x) => x.value === k)?.label ?? k;

async function load() {
  error.value = "";
  try {
    types.value = await relationTypes(worldSlug.value);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(worldSlug, load, { immediate: true });

async function run(fn: () => Promise<unknown>) {
  error.value = "";
  try {
    await fn();
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

const aKind = ref("character");
const bKind = ref("character");
const label = ref("");
const reverse = ref("");
function add() {
  if (!label.value.trim()) return;
  const body = { a_kind: aKind.value, b_kind: bKind.value, label: label.value, reverse_label: reverse.value.trim() || null };
  label.value = reverse.value = "";
  void run(() => addRelationType(worldSlug.value, body));
}

const groups = computed(() => {
  const out = new Map<string, RelationType[]>();
  for (const t of types.value) {
    const key = `${kindLabel(t.a_kind)} → ${kindLabel(t.b_kind)}`;
    out.set(key, [...(out.get(key) ?? []), t]);
  }
  return [...out.entries()];
});
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs"><RouterLink :to="{ name: 'bible', params: { world: world.slug } }">Bible</RouterLink></div>
        <h1>Kinds of relationship</h1>
        <p class="muted">
          How entries can be connected. Each reads one way from the first side and, if you give it one, another way back:
          “parent of” / “child of”. Leave the reverse empty when it reads the same both ways, like “married to”.
        </p>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <form class="card form wide" @submit.prevent="add">
      <div class="actions">
        <select v-model="aKind" class="filter" aria-label="From kind">
          <option v-for="k in KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
        <input v-model="label" class="filter grow" placeholder="reads as, e.g. apprenticed to" aria-label="Label" maxlength="100" required />
        <select v-model="bKind" class="filter" aria-label="To kind">
          <option v-for="k in KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
      </div>
      <div class="actions">
        <input v-model="reverse" class="filter grow" placeholder="and back, e.g. master of (optional)" aria-label="Reverse label" maxlength="100" />
        <button class="btn btn-primary btn-sm" type="submit" :disabled="!label.trim()">Add</button>
      </div>
    </form>

    <section v-for="[pair, list] in groups" :key="pair" class="card">
      <h2 class="small muted">{{ pair }}</h2>
      <ul class="rows" data-testid="relation-types">
        <li v-for="t in list" :key="t.id">
          <span class="grow">
            <InlineText :value="t.label" label="Label" :maxlength="100" @save="(v) => v && run(() => updateRelationType(world!.slug, t.id, { label: v }))" />
            <span class="muted"> / </span>
            <InlineText
              :value="t.reverse_label ?? ''"
              label="Reverse"
              placeholder="same both ways"
              :maxlength="100"
              @save="(v) => run(() => updateRelationType(world!.slug, t.id, { reverse_label: v || null }))"
            />
          </span>
          <label class="small check" :title="'Its relationships carry a role in the group (member of the Lamp Guild · Captain)'">
            <input type="checkbox" :checked="t.has_role" data-testid="has-role" @change="run(() => updateRelationType(world!.slug, t.id, { has_role: ($event.target as HTMLInputElement).checked }))" /> has a role
          </label>
          <span class="muted small">{{ t.used ? `used ${t.used}×` : "unused" }}</span>
          <button
            type="button"
            class="icon-btn small"
            :disabled="t.used > 0"
            :title="t.used ? 'In use; change or remove those relationships first' : 'Remove'"
            :aria-label="`Remove ${t.label}`"
            @click="run(() => deleteRelationType(world!.slug, t.id))"
          >
            ×
          </button>
        </li>
      </ul>
    </section>
  </template>
</template>
