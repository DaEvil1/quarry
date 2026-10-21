<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { createEntity, listEntities } from "../bible";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type Entity, type EntityKind } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const entities = ref<Entity[]>([]);
const q = ref("");
const kindFilter = ref<EntityKind | "">("");
const error = ref("");

const newName = ref("");
const newKind = ref<EntityKind>("character");
const busy = ref(false);

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

const groups = computed(() => {
  const needle = q.value.trim().toLowerCase();
  const shown = entities.value.filter(
    (e) =>
      (!kindFilter.value || e.kind === kindFilter.value) &&
      (!needle || e.name.toLowerCase().includes(needle) || e.aliases.some((a) => a.toLowerCase().includes(needle))),
  );
  return ENTITY_KINDS.map((k) => ({ ...k, items: shown.filter((e) => e.kind === k.value) })).filter((g) => g.items.length);
});

async function add() {
  busy.value = true;
  error.value = "";
  try {
    const e = await createEntity(worldSlug.value, { name: newName.value, kind: newKind.value });
    newName.value = "";
    await router.push({ name: "entity", params: { world: worldSlug.value, id: e.id } });
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Bible</h1>
        <p class="muted">Characters, places and terms shared by every project in this world.</p>
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
      </div>
      <div class="actions">
        <button class="btn btn-primary" type="submit" :disabled="busy">Add to the bible</button>
      </div>
    </form>

    <div class="toolbar">
      <div class="field grow">
        <label for="bible-search" class="visually-hidden">Search</label>
        <input id="bible-search" v-model="q" type="search" class="filter search" placeholder="Search names and spellings" />
      </div>
      <select v-model="kindFilter" class="filter" aria-label="Kind">
        <option value="">All kinds</option>
        <option v-for="k in ENTITY_KINDS" :key="k.value" :value="k.value">{{ k.plural }}</option>
      </select>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-for="g in groups" :key="g.value" class="card">
      <h2 class="small muted">{{ g.plural }}</h2>
      <ul class="rows" data-testid="bible-list">
        <li v-for="e in g.items" :key="e.id">
          <RouterLink class="grow" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
          <span v-if="e.aliases.length" class="muted small">also {{ e.aliases.join(", ") }}</span>
          <span class="pill" :title="`${e.mention_count} mentions`">{{ e.mention_count }}</span>
        </li>
      </ul>
    </section>
    <p v-if="!groups.length && !error" class="empty">
      {{ entities.length ? "Nothing matches." : "The bible is empty. Add the first name above." }}
    </p>
  </template>
</template>
