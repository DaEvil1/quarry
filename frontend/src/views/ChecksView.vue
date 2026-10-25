<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { endBefore, setLabelSwitches } from "../bible";
import { checks, resolutions, resolve, unresolve, type Check, type Resolution } from "../companion";
import { useSession } from "../stores/session";
import NotFoundView from "./NotFoundView.vue";

// Checks: the continuity rules over what is recorded, for the whole world, chapter by chapter. Each is resolved
// rather than dismissed: fixed (it goes away), intentional (never flagged again) or later (kept on a list).
const route = useRoute();
const session = useSession();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const list = ref<Check[]>([]);
const settled = ref<Resolution[]>([]);
const error = ref("");
const loaded = ref(false);

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    [list.value, settled.value] = await Promise.all([checks(worldSlug.value), resolutions(worldSlug.value)]);
    loaded.value = true;
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(worldSlug, load, { immediate: true });

const open = computed(() => list.value.filter((c) => !c.later));
const later = computed(() => list.value.filter((c) => c.later));
const groups = computed(() => {
  const out: { title: string; id: string | null; items: Check[] }[] = [];
  for (const c of open.value) {
    const key = c.chapter?.id ?? null;
    const g = out.find((x) => x.id === key);
    if (g) g.items.push(c);
    else out.push({ title: c.chapter?.title ?? "The whole world", id: key, items: [c] });
  }
  return out;
});
const intentional = computed(() => settled.value.filter((r) => r.outcome === "intentional" && !["unrecorded", "echo", "long_sentence", "doubled", "where", "missing_label", "crossover"].includes(r.rule)));

async function settle(c: Check, outcome: "intentional" | "later") {
  await resolve(worldSlug.value, c.rule, c.key, outcome);
  await load();
}
// a conflict that is two true values (eye colour green and red): the label holds several values for the kind
async function bothTrue(c: Check) {
  if (!c.label || !c.kind) return;
  try {
    await setLabelSwitches(worldSlug.value, c.kind, c.label, { several: true });
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
// two holders of a one-at-a-time role: the earlier one ends where the later one starts (a handover)
async function handOver(c: Check) {
  if (!c.end || !c.before) return;
  try {
    await endBefore(worldSlug.value, c.end.id, c.before.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
async function reopen(r: Resolution) {
  await unresolve(worldSlug.value, r.id);
  await load();
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">{{ world.name }}</div>
        <h1>Checks</h1>
        <p class="muted">
          What the recorded facts, relationships and chapters say against each other: named after being recorded dead,
          named before being born, two values of a fact at once, two holders of a role only one may hold, a point of
          view who isn't in their chapter, places inside themselves, dates that run backwards. Nothing is guessed from
          the prose.
        </p>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <p v-if="loaded && !open.length" class="empty" data-testid="checks-empty">Nothing to check. Everything recorded agrees.</p>

    <section v-for="g in groups" :key="g.id ?? 'world'" class="card" data-testid="check-group">
      <h2 class="small muted">
        <RouterLink v-if="g.id" :to="{ name: 'chapter', params: { world: world.slug, id: g.id } }">{{ g.title }}</RouterLink>
        <template v-else>{{ g.title }}</template>
      </h2>
      <ul class="rows">
        <li v-for="c in g.items" :key="c.rule + c.key" data-testid="check">
          <span class="grow">{{ c.message }}</span>
          <RouterLink v-for="e in c.entities" :key="e.id" class="kname small" :class="`k-${e.kind}`" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
          <button v-if="c.rule === 'fact_conflict' && c.label && c.kind" type="button" class="btn btn-sm" title="The label holds several values at once for this kind" @click="bothTrue(c)">Both are true (several values)</button>
          <button v-if="c.rule === 'role_clash' && c.end && c.before" type="button" class="btn btn-sm" data-testid="end-before" @click="handOver(c)">End {{ c.end.name }}'s before {{ c.before.name }}'s</button>
          <button type="button" class="btn btn-sm" title="Planted on purpose: never flag it again" @click="settle(c, 'intentional')">Intentional</button>
          <button type="button" class="btn btn-sm" @click="settle(c, 'later')">Later</button>
        </li>
      </ul>
    </section>

    <section v-if="later.length" class="card">
      <h2 class="small muted">Later</h2>
      <ul class="rows" data-testid="checks-later">
        <li v-for="c in later" :key="c.rule + c.key">
          <span class="grow">{{ c.message }}</span>
          <RouterLink v-if="c.chapter" class="small" :to="{ name: 'chapter', params: { world: world.slug, id: c.chapter.id } }">{{ c.chapter.title }}</RouterLink>
          <button type="button" class="btn btn-sm" @click="settle(c, 'intentional')">Intentional</button>
        </li>
      </ul>
    </section>

    <details v-if="intentional.length" class="card">
      <summary class="small muted">{{ intentional.length }} marked intentional</summary>
      <ul class="rows">
        <li v-for="r in intentional" :key="r.id">
          <span class="grow small muted">{{ r.rule.replace(/_/g, " ") }}{{ r.note ? `: ${r.note}` : "" }}</span>
          <button type="button" class="btn btn-sm" @click="reopen(r)">Check it again</button>
        </li>
      </ul>
    </details>
  </template>
</template>
