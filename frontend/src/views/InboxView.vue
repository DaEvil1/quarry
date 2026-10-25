<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";

import FollowUpStep from "../components/FollowUpStep.vue";
import ItemRow from "../components/ItemRow.vue";
import ProjectFilter from "../components/ProjectFilter.vue";
import UndoToast from "../components/UndoToast.vue";
import { get } from "../api";
import { listItems } from "../items";
import { useOutbox } from "../stores/outbox";
import { useSession } from "../stores/session";
import { WORLD_ONLY, type Item } from "../types";
import NotFoundView from "./NotFoundView.vue";

type Tab = "open" | "deferred" | "closed";

const route = useRoute();
const session = useSession();
const outbox = useOutbox();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const tab = ref<Tab>("open");
const project = ref(typeof route.query.project === "string" ? route.query.project : "");
const items = ref<Item[]>([]);
const loading = ref(false);
const error = ref("");
const openId = ref<string | null>(null);
const toast = ref<{ label: string; undo: () => Promise<void> } | null>(null);

// captures still on this device show at the top of the open list, under the same project filter
const pending = computed(() =>
  tab.value === "open"
    ? outbox.forWorld(worldSlug.value).filter((p) => !project.value || (p.project ?? WORLD_ONLY) === project.value)
    : [],
);

async function load() {
  if (!world.value) return;
  loading.value = true;
  error.value = "";
  try {
    items.value = await listItems(worldSlug.value, { status: tab.value, project: project.value || undefined });
  } catch (e) {
    error.value = session.offline || !outbox.online
      ? "You're offline. The inbox loads when you're back; captures still save on this device."
      : (e as Error).message;
  } finally {
    loading.value = false;
  }
}
watch([worldSlug, tab, project], load, { immediate: true });

async function refreshItem(id: string) {
  try {
    changed(await get<Item>(`/api/worlds/${encodeURIComponent(worldSlug.value)}/items/${id}`));
  } catch {
    await load();
  }
  void session.refreshNearMisses(worldSlug.value);
}

function changed(item: Item) {
  items.value = items.value.map((i) => (i.id === item.id ? item : i));
}

// the follow-up step after a close with a decision line (docs/SPEC.md §16.3): chips where the closed item was, only
// online; tapping anywhere else, or scrolling it out of sight, skips it
const step = ref<{ at: number; decision: { id: string; text: string }; made: string[] } | null>(null);
const stepEl = ref<HTMLElement | null>(null);
const setStepEl = (el: unknown) => {
  if (el) stepEl.value = el as HTMLElement;
};
function endStep() {
  step.value = null;
  stepEl.value = null;
}
function outside(e: Event) {
  if (step.value && stepEl.value && !stepEl.value.contains(e.target as Node) && !(e.target as HTMLElement).closest?.(".toast")) endStep();
}
function scrolled() {
  const r = stepEl.value?.getBoundingClientRect();
  if (step.value && r && (r.bottom < 0 || r.top > window.innerHeight)) endStep();
}
window.addEventListener("pointerdown", outside, true);
window.addEventListener("scroll", scrolled, { passive: true });
onBeforeUnmount(() => {
  window.removeEventListener("pointerdown", outside, true);
  window.removeEventListener("scroll", scrolled);
});

function moved(item: Item, label: string, undo: (made?: string[]) => Promise<void>, decision?: { id: string; text: string }) {
  const at = items.value.findIndex((i) => i.id === item.id);
  items.value = items.value.filter((i) => i.id !== item.id);
  openId.value = null;
  const made: string[] = [];
  step.value = decision && !session.offline && outbox.online ? { at: Math.max(0, at), decision, made } : null;
  toast.value = { label, undo: async () => { endStep(); await undo(made); await load(); } };
  void session.refreshCounts(worldSlug.value);
}

const counts = computed(() => (session.counts?.world === worldSlug.value ? session.counts : null));
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Inbox</h1>
      </div>
      <div class="actions">
        <RouterLink class="btn btn-sm desk-only" :to="{ name: 'triage', params: { world: world.slug } }">
          Start triage
        </RouterLink>
        <RouterLink class="btn btn-sm btn-primary" :to="{ name: 'capture', params: { world: world.slug } }">
          Capture
        </RouterLink>
      </div>
    </div>

    <div class="toolbar">
      <div class="tabs" role="tablist">
        <button
          v-for="t in ['open', 'deferred', 'closed'] as const"
          :key="t"
          type="button"
          role="tab"
          :aria-selected="tab === t"
          class="tab"
          @click="tab = t"
        >
          {{ { open: "Open", deferred: "Deferred", closed: "Closed" }[t] }}
          <span v-if="t === 'open' && counts" class="count">{{ counts.open }}</span>
          <span v-if="t === 'deferred' && counts?.deferred" class="count">{{ counts.deferred }}</span>
        </button>
      </div>
      <ProjectFilter v-model="project" :world="world" />
    </div>

    <div v-if="error" class="notice warn" role="status">{{ error }}</div>

    <section class="card list-card">
      <ul class="items" data-testid="inbox-list">
        <li v-for="p in pending" :key="p.id" class="item pending">
          <div class="item-head">
            <span class="pill" :class="`kind-${p.kind}`">{{ p.kind }}</span>
            <span class="item-line">{{ p.body.split("\n", 1)[0] }}</span>
            <span class="pill" :class="p.error ? 'warn' : 'accent'">{{ p.error ? "Refused" : "Waiting to sync" }}</span>
          </div>
        </li>
        <template v-for="(i, n) in items" :key="i.id">
          <li v-if="step && step.at === n" :ref="setStepEl" class="item fu-inbox">
            <FollowUpStep :world="world.slug" :decision="step.decision" lead="Decision logged" autofocus @added="(a) => a.made && step?.made.push(a.followup.id)" @done="endStep" />
          </li>
          <ItemRow
            :item="i"
            :world="world"
            :open="openId === i.id"
            @toggle="openId = openId === i.id ? null : i.id"
            @changed="changed"
            @moved="moved"
            @refresh="refreshItem(i.id)"
          />
        </template>
        <li v-if="step && step.at >= items.length" :ref="setStepEl" class="item fu-inbox">
          <FollowUpStep :world="world.slug" :decision="step.decision" lead="Decision logged" autofocus @added="(a) => a.made && step?.made.push(a.followup.id)" @done="endStep" />
        </li>
      </ul>
      <p v-if="!loading && !error && !items.length && !pending.length" class="empty">
        {{ tab === "open" ? "Nothing waiting. Capture something." : tab === "deferred" ? "Nothing deferred." : "Nothing closed yet." }}
      </p>
    </section>

    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" @dismiss="toast = null" />
  </template>
</template>
