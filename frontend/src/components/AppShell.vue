<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { focusOf, writeLastPlace } from "../focus";
import { readLastUsed, writeLastUsed } from "../lastUsed";
import { syncWorld } from "../offline";
import { ENTITY_KINDS } from "../types";
import { useCards } from "../world/cards";
import { useOutbox } from "../stores/outbox";
import { useSession } from "../stores/session";
import GuideOverlay from "./GuideOverlay.vue";
import Icon from "./Icon.vue";
import UpdateBar from "./UpdateBar.vue";
import WorldSwitcher from "./WorldSwitcher.vue";

const session = useSession();
const cards = useCards();
// the kinds of things this world has, for the nav (characters and places always, the rest once they exist)
const kinds = computed(() =>
  ENTITY_KINDS.filter((k) => k.value === "character" || k.value === "place" || cards.counts[k.value]).map((k) => ({
    ...k,
    count: cards.counts[k.value] ?? 0,
  })),
);
const outbox = useOutbox();
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

// the last place used in each world, for opening it there under Writing (docs/SPEC.md §14.9)
watch(
  () => route.fullPath,
  (path) => {
    if (worldSlug.value && route.name !== "world" && route.name !== "not-found") writeLastPlace(worldSlug.value, path);
  },
  { immediate: true },
);
// the nav's groups in the focus's order: Writing puts the projects first, Planning the planning links (with the
// Journal at their head and the Timeline after Decisions); nothing is hidden under either
const planning = computed(() => focusOf(world.value) === "planning");
const groups = computed(() => (planning.value ? ["planning", "world", "projects"] : ["projects", "planning", "world"]));

// the inbox count in the nav follows the world on screen, and catches up when captures sync
watch(
  world,
  (w) => {
    if (!w) return;
    void session.refreshCounts(w.slug);
    void session.refreshNearMisses(w.slug);
    // a Guide sandbox is deleted when its walkthrough ends: no offline copy
    if (!w.sandbox) void syncWorld(w.slug).catch(() => undefined);
    void cards.load(w.slug);
  },
  { immediate: true },
);
// keep the offline copy fresh: when the connection is back, and every 15 minutes
const resync = () => world.value && !world.value.sandbox && void syncWorld(world.value.slug).catch(() => undefined);
watch(() => outbox.online, (online) => online && resync());
const syncTimer = setInterval(resync, 15 * 60_000);
onBeforeUnmount(() => clearInterval(syncTimer));
watch(
  () => outbox.waiting,
  (now, before) => {
    if (world.value && now < before) void session.refreshCounts(world.value.slug);
  },
);
const openCount = computed(() =>
  world.value && session.counts?.world === world.value.slug ? session.counts.open : null,
);

const nearMissCount = computed(() =>
  world.value && session.nearMisses?.world === world.value.slug ? session.nearMisses.words : 0,
);
const to = (name: string) => (world.value ? { name, params: { world: world.value.slug } } : { name: "home" });
const tabActive = (...names: string[]) => names.includes(String(route.name));
const offline = computed(() => !outbox.online || session.offline);

async function signOut() {
  if (outbox.waiting && !confirm(`${outbox.waiting} capture(s) haven't synced yet and stay on this device. Sign out anyway?`)) {
    return;
  }
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
          <RouterLink :to="to('world')">
            <Icon name="world" /><span>Overview</span>
          </RouterLink>
          <template v-for="g in groups" :key="g">
            <template v-if="g === 'planning'">
              <RouterLink v-if="planning" :to="to('journal')" data-testid="nav-journal">
                <Icon name="journal" /><span>Journal</span>
              </RouterLink>
              <RouterLink :to="to('capture')">
                <Icon name="capture" /><span>Capture</span>
              </RouterLink>
              <RouterLink :to="to('inbox')" data-testid="nav-inbox">
                <Icon name="inbox" /><span>Inbox</span>
                <span v-if="openCount" class="badge">{{ openCount }}</span>
              </RouterLink>
              <RouterLink :to="to('triage')">
                <Icon name="triage" /><span>Triage</span>
              </RouterLink>
              <RouterLink :to="to('decisions')">
                <Icon name="decisions" /><span>Decisions</span>
              </RouterLink>
              <RouterLink v-if="planning" :to="to('timeline')" data-testid="nav-timeline">
                <Icon name="timeline" /><span>Timeline</span>
              </RouterLink>
              <RouterLink v-if="!planning" :to="to('journal')" data-testid="nav-journal">
                <Icon name="journal" /><span>Journal</span>
              </RouterLink>
            </template>
            <template v-else-if="g === 'world'">
              <div class="nav-title">World</div>
              <RouterLink
                v-for="k in kinds"
                :key="k.value"
                :to="world ? { name: 'bible-kind', params: { world: world.slug, kind: k.value } } : { name: 'home' }"
                :class="`k-${k.value}`"
                :data-testid="`nav-kind-${k.value}`"
              >
                <span class="kdot nav-kdot" /><span>{{ k.plural }}</span>
                <span v-if="k.count" class="badge dim">{{ k.count }}</span>
              </RouterLink>
              <RouterLink :to="to('bible')">
                <Icon name="bible" /><span>All entries</span>
              </RouterLink>
              <RouterLink :to="to('graph')" data-testid="nav-graph">
                <Icon name="graph" /><span>Graph</span>
              </RouterLink>
              <RouterLink :to="to('chart')" data-testid="nav-chart">
                <Icon name="chart" /><span>Chart</span>
              </RouterLink>
              <RouterLink v-if="!planning" :to="to('timeline')" data-testid="nav-timeline">
                <Icon name="timeline" /><span>Timeline</span>
              </RouterLink>
              <RouterLink :to="to('where')" data-testid="nav-where">
                <Icon name="where" /><span>Where everyone is</span>
              </RouterLink>
              <RouterLink :to="to('checks')" data-testid="nav-checks">
                <Icon name="checks" /><span>Checks</span>
              </RouterLink>
              <RouterLink :to="to('names')" data-testid="nav-names">
                <Icon name="names" /><span>Name check</span>
                <span v-if="nearMissCount" class="badge warn">{{ nearMissCount }}</span>
              </RouterLink>
            </template>
            <template v-else>
              <div class="nav-title">Projects</div>
              <RouterLink
                v-for="p in world.projects"
                :key="p.id"
                :to="{ name: 'project', params: { world: world.slug, project: p.slug } }"
                data-testid="nav-project"
              >
                <Icon name="project" /><span>{{ p.name }}</span>
                <span v-if="session.counts?.world === world.slug && session.counts.open_by_project[p.slug]" class="badge dim">
                  {{ session.counts.open_by_project[p.slug] }}
                </span>
              </RouterLink>
              <p v-if="!world.projects.length" class="nav-empty">No projects yet</p>
            </template>
          </template>
        </template>
      </nav>
      <div class="nav-foot">
        <RouterLink :to="{ name: 'settings' }" data-testid="nav-settings"><Icon name="settings" /> {{ session.user?.display_name }}</RouterLink>
        <RouterLink :to="{ name: 'guide' }" data-testid="nav-guide">Guide</RouterLink>
        <button type="button" class="linkish" @click="signOut">Sign out</button>
      </div>
    </aside>

    <header class="topbar">
      <RouterLink class="brand" to="/" aria-label="Quarry home"><img src="/favicon.svg" alt="" /></RouterLink>
      <WorldSwitcher :worlds="session.worlds" :current="world" />
    </header>

    <main :class="`page-${route.meta.width ?? 'read'}`">
      <div class="page">
      <UpdateBar />
      <div v-if="offline" class="notice offline" role="status" data-testid="offline">
        Offline. Captures and cuts are kept on this device and sync when you're back.
        <template v-if="outbox.waiting"> {{ outbox.waiting }} waiting.</template>
      </div>
      <div v-else-if="outbox.needsSignIn" class="notice warn" role="status">
        Sign in again to send {{ outbox.waiting }} capture(s) saved on this device.
        <RouterLink to="/login">Sign in</RouterLink>
      </div>
      <RouterView />
      </div>
    </main>
    <GuideOverlay />

    <nav class="tabbar" aria-label="Sections">
      <RouterLink :to="to('capture')" :class="{ active: tabActive('capture') }">
        <Icon name="capture" />Capture
      </RouterLink>
      <RouterLink :to="to('inbox')" :class="{ active: tabActive('inbox', 'triage', 'decisions', 'item') }">
        <Icon name="inbox" />Inbox<span v-if="openCount" class="tab-badge">{{ openCount }}</span>
      </RouterLink>
      <RouterLink :to="to('bible')" :class="{ active: tabActive('bible', 'entity', 'names') }">
        <Icon name="bible" />Bible
      </RouterLink>
      <RouterLink :to="to('world')" :class="{ active: tabActive('world', 'project', 'new-world') }">
        <Icon name="world" />World
      </RouterLink>
      <RouterLink :to="{ name: 'settings' }" :class="{ active: tabActive('settings') }">
        <Icon name="settings" />Settings
      </RouterLink>
    </nav>
  </div>
</template>
