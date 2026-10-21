<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { fixes, nearMisses, sourceLink } from "../bible";
import { useSession } from "../stores/session";
import type { NearMissGroup } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const session = useSession();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const groups = ref<NearMissGroup[]>([]);
const loaded = ref(false);
const error = ref("");
const done = ref("");

const SOURCE_LABEL: Record<string, string> = { item: "Item", decision: "Decision", journal: "Journal", entity: "Bible" };

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    groups.value = await nearMisses(worldSlug.value);
    session.nearMisses = { world: worldSlug.value, words: groups.value.length };
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loaded.value = true;
  }
}
watch(worldSlug, load, { immediate: true });

// the three fixes, as plain functions for the template
const fixReplace = fixes.replace;
const fixSpelling = (world: string, token: string, entityId: string) => fixes.addSpelling(world, token, entityId);
const fixIgnore = fixes.notATypo;

async function act(fn: () => Promise<unknown>, message: string) {
  error.value = "";
  try {
    await fn();
    done.value = message;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Name check</h1>
        <p class="muted">Words that look like misspelled names from the bible.</p>
      </div>
    </div>

    <div v-if="done" class="notice ok" role="status">{{ done }}</div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-for="g in groups" :key="`${g.token}-${g.entity.id}`" class="card" data-testid="near-miss-group">
      <div class="card-head">
        <h2>
          <span class="near-miss static">{{ g.token }}</span>
          <span class="muted"> → </span>
          <RouterLink :to="{ name: 'entity', params: { world: world.slug, id: g.entity.id } }">{{ g.entity.name }}</RouterLink>
        </h2>
        <span class="muted small">{{ g.count }}×</span>
      </div>
      <div class="actions">
        <button type="button" class="btn btn-sm btn-primary" @click="act(() => fixReplace(world!.slug, g.token, g.entity.id), `Replaced ${g.token} with ${g.entity.name}.`)">
          Replace everywhere
        </button>
        <button type="button" class="btn btn-sm" @click="act(() => fixSpelling(world!.slug, g.token, g.entity.id), `${g.token} is now a spelling of ${g.entity.name}.`)">
          It's another spelling
        </button>
        <button type="button" class="btn btn-sm" @click="act(() => fixIgnore(world!.slug, g.token), `${g.token} won't be flagged again.`)">
          Not a typo
        </button>
      </div>
      <ul class="rows">
        <li v-for="(s, i) in g.sources" :key="i">
          <div class="grow">
            <div class="snippet">{{ s.snippet.before }}<mark class="near-miss static">{{ s.snippet.match }}</mark>{{ s.snippet.after }}</div>
            <RouterLink class="small" :to="sourceLink(world.slug, s.source_table, s.source_id)">{{ SOURCE_LABEL[s.source_table] }}: {{ s.title }}</RouterLink>
          </div>
        </li>
      </ul>
    </section>
    <p v-if="loaded && !groups.length && !error" class="empty">No likely misspellings. Everything matches the bible.</p>
  </template>
</template>
