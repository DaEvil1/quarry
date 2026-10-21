<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { readLastUsed, writeLastUsed } from "../lastUsed";
import { useSession } from "../stores/session";
import WorldSwitcher from "./WorldSwitcher.vue";

const session = useSession();
const route = useRoute();
const router = useRouter();

const worldSlug = computed(() => (typeof route.params.world === "string" ? route.params.world : undefined));
const projectSlug = computed(() => (typeof route.params.project === "string" ? route.params.project : undefined));
// outside a world's pages (settings, say) the nav keeps showing the world last opened
const world = computed(() => {
  const slug = worldSlug.value ?? readLastUsed().world;
  return slug ? session.world(slug) : undefined;
});

// remember where we are, so the next visit to "/" opens it again
watch(
  [world, projectSlug],
  ([w, p]) => {
    if (w && worldSlug.value) writeLastUsed({ world: w.slug, project: p && session.project(w.slug, p) ? p : undefined });
  },
  { immediate: true },
);

const worldLink = computed(() => (world.value ? { name: "world", params: { world: world.value.slug } } : { name: "home" }));
const onWorldTab = computed(() => route.name === "world" || route.name === "project" || route.name === "new-world");

async function signOut() {
  await session.signOut();
  await router.push("/login");
}
</script>

<template>
  <div class="shell">
    <aside class="nav" aria-label="Main">
      <RouterLink class="brand" to="/"><img src="/favicon.svg" alt="" />Quarry</RouterLink>
      <WorldSwitcher :worlds="session.worlds" :current="world" />
      <nav>
        <template v-if="world">
          <RouterLink :to="{ name: 'world', params: { world: world.slug } }">
            <span class="ico" aria-hidden="true">◇</span><span>Overview</span>
          </RouterLink>
          <div class="nav-title">Projects</div>
          <RouterLink
            v-for="p in world.projects"
            :key="p.id"
            :to="{ name: 'project', params: { world: world.slug, project: p.slug } }"
          >
            <span class="ico" aria-hidden="true">▤</span><span>{{ p.name }}</span>
          </RouterLink>
          <p v-if="!world.projects.length" class="nav-empty">No projects yet</p>
        </template>
      </nav>
      <div class="nav-foot">
        <RouterLink :to="{ name: 'settings' }" data-testid="nav-settings">⚙ {{ session.user?.display_name }}</RouterLink>
        <button type="button" class="linkish" @click="signOut">Sign out</button>
      </div>
    </aside>

    <header class="topbar">
      <RouterLink class="brand" to="/" aria-label="Quarry home"><img src="/favicon.svg" alt="" /></RouterLink>
      <WorldSwitcher :worlds="session.worlds" :current="world" />
    </header>

    <main>
      <RouterView />
    </main>

    <nav class="tabbar" aria-label="Sections">
      <RouterLink :to="worldLink" :class="{ active: onWorldTab }">
        <span class="ico" aria-hidden="true">◇</span>World
      </RouterLink>
      <RouterLink :to="{ name: 'settings' }" :class="{ active: route.name === 'settings' }">
        <span class="ico" aria-hidden="true">⚙</span>Settings
      </RouterLink>
    </nav>
  </div>
</template>
