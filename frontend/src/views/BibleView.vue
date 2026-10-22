<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { createEntity, listEntities } from "../bible";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type Entity, type EntityKind } from "../types";
import { useCards } from "../world/cards";
import NotFoundView from "./NotFoundView.vue";

// The bible: every entry, or one kind of them (characters, places, …) as a table with their one-liners and the facts
// most of them have.
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const kind = computed(() => (route.params.kind ? (String(route.params.kind) as EntityKind) : null));
const kindInfo = computed(() => ENTITY_KINDS.find((k) => k.value === kind.value) ?? null);
const entities = ref<Entity[]>([]);
const q = ref("");
const error = ref("");

const newName = ref("");
const newKind = ref<EntityKind>("character");
const busy = ref(false);
watch(kind, (k) => (newKind.value = k ?? "character"), { immediate: true });

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    entities.value = await listEntities(worldSlug.value);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(worldSlug, load, { immediate: true });

const shown = computed(() => {
  const needle = q.value.trim().toLowerCase();
  return entities.value.filter(
    (e) =>
      (!kind.value || e.kind === kind.value) &&
      (!needle ||
        e.name.toLowerCase().includes(needle) ||
        e.summary.toLowerCase().includes(needle) ||
        e.aliases.some((a) => a.toLowerCase().includes(needle))),
  );
});

const groups = computed(() =>
  ENTITY_KINDS.map((k) => ({ ...k, items: shown.value.filter((e) => e.kind === k.value) })).filter((g) => g.items.length),
);

/** On a kind's page: up to three fact labels that at least two of its entries have, as extra columns. */
const columns = computed(() => {
  if (!kind.value) return [];
  const seen = new Map<string, number>();
  for (const c of cards.cards) if (c.kind === kind.value) for (const f of c.facts) seen.set(f.label, (seen.get(f.label) ?? 0) + 1);
  return [...seen.entries()]
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([label]) => label);
});
const factOf = (id: string, label: string) => cards.byId.get(id)?.facts.find((f) => f.label === label)?.value ?? "";

async function add() {
  busy.value = true;
  error.value = "";
  try {
    const e = await createEntity(worldSlug.value, { name: newName.value, kind: newKind.value });
    newName.value = "";
    void cards.refresh(worldSlug.value);
    await router.push({ name: "entity", params: { world: worldSlug.value, id: e.id } });
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <NotFoundView v-if="!world || (kind && !kindInfo)" what="world" />
  <template v-else>
    <div class="page-head" :class="kind ? `k-${kind}` : ''">
      <div>
        <div class="crumbs">
          <RouterLink v-if="kind" :to="{ name: 'bible', params: { world: world.slug } }">Bible</RouterLink>
          <template v-else>{{ world.name }}</template>
        </div>
        <h1><span v-if="kind" class="kdot" />{{ kindInfo?.plural ?? "Bible" }}</h1>
        <p v-if="!kind" class="muted">Everything shared by every project in this world.</p>
      </div>
      <div class="actions">
        <RouterLink class="btn btn-sm" :to="{ name: 'relation-types', params: { world: world.slug } }">Kinds of relationship</RouterLink>
      </div>
    </div>

    <form class="card form wide" @submit.prevent="add">
      <div class="actions">
        <div class="field grow">
          <label for="new-entity">New entry</label>
          <input id="new-entity" v-model="newName" type="text" maxlength="200" required placeholder="Name" />
        </div>
        <div class="field">
          <label for="new-kind">Kind</label>
          <select id="new-kind" v-model="newKind">
            <option v-for="k in ENTITY_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </div>
        <button class="btn btn-primary" type="submit" :disabled="busy">Add to the bible</button>
      </div>
    </form>

    <div class="toolbar">
      <div class="field grow">
        <label for="bible-search" class="visually-hidden">Search</label>
        <input id="bible-search" v-model="q" type="search" class="filter search" placeholder="Search names, spellings and one-liners" />
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-if="kind && shown.length" class="card table-card" :class="`k-${kind}`">
      <table class="bible-table" data-testid="bible-list">
        <thead>
          <tr>
            <th>Name</th>
            <th>In one line</th>
            <th v-for="c in columns" :key="c">{{ c }}</th>
            <th class="num" title="Mentions">#</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in shown" :key="e.id">
            <td>
              <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
              <div v-if="e.aliases.length" class="muted small">{{ e.aliases.join(", ") }}</div>
            </td>
            <td class="muted">{{ e.summary }}</td>
            <td v-for="c in columns" :key="c">{{ factOf(e.id, c) }}</td>
            <td class="num muted">{{ e.mention_count }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <template v-else-if="!kind">
      <section v-for="g in groups" :key="g.value" class="card" :class="`k-${g.value}`">
        <h2 class="small muted">
          <RouterLink :to="{ name: 'bible-kind', params: { world: world.slug, kind: g.value } }"><span class="kdot" />{{ g.plural }}</RouterLink>
        </h2>
        <ul class="rows" data-testid="bible-list">
          <li v-for="e in g.items" :key="e.id">
            <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
            <span class="grow muted small ellipsis">{{ e.summary }}</span>
            <span v-if="e.aliases.length" class="muted small">also {{ e.aliases.join(", ") }}</span>
            <span class="pill" :title="`${e.mention_count} mentions`">{{ e.mention_count }}</span>
          </li>
        </ul>
      </section>
    </template>

    <p v-if="!shown.length && !error" class="empty">
      {{ entities.length && (q || !kind) ? "Nothing matches." : kind ? `No ${kindInfo?.plural.toLowerCase()} yet.` : "The bible is empty. Add the first name above." }}
    </p>
  </template>
</template>
