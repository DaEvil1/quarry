<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get } from "../api";
import ItemRow from "../components/ItemRow.vue";
import { useSession } from "../stores/session";
import type { Item } from "../types";
import NotFoundView from "./NotFoundView.vue";

// One item on its own page: where mentions and tags in the bible link to.
const route = useRoute();
const session = useSession();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const item = ref<Item | null>(null);
const missing = ref(false);
const note = ref("");

async function load() {
  missing.value = false;
  try {
    item.value = await get<Item>(`/api/worlds/${encodeURIComponent(worldSlug.value)}/items/${String(route.params.id)}`);
  } catch {
    missing.value = true;
  }
}
watch(() => route.params.id, load, { immediate: true });

async function moved(_i: Item, label: string) {
  note.value = label;
  await load();
}
</script>

<template>
  <NotFoundView v-if="!world || missing" what="item" />
  <template v-else-if="item">
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'inbox', params: { world: world.slug } }">Inbox</RouterLink>
        </div>
        <h1>Item</h1>
      </div>
    </div>
    <div v-if="note" class="notice ok" role="status">{{ note }}</div>
    <section class="card list-card">
      <ul class="items">
        <ItemRow :item="item" :world="world" :open="true" @toggle="() => {}" @changed="(i) => (item = i)" @moved="moved" @refresh="load" />
      </ul>
    </section>
  </template>
</template>
