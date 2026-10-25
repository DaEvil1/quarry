<script setup lang="ts">
// The Guide (docs/SPEC.md §15): short walkthroughs of what Quarry does, each on a fresh sandbox copy of the demo
// world. Watch one play itself, or try it with each step waiting for you. Nothing here runs unless asked.
import { computed } from "vue";

import { TOURS } from "../guide/tours";
import { useGuide, type Spotlight } from "../stores/guide";
import { useSession } from "../stores/session";

const guide = useGuide();
const session = useSession();
const sandbox = computed(() => session.worlds.find((w) => w.sandbox));
const resumable = computed(() => {
  const at = guide.resumable;
  const tour = at && TOURS.find((t) => t.id === at.tour);
  return tour && sandbox.value?.slug === at.slug ? { title: tour.title, step: at.index + 1 } : null;
});
const doneOn = (id: string) => {
  const at = guide.done[id];
  return at ? new Date(at).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "";
};
const SPOTLIGHT: { value: Spotlight; label: string }[] = [
  { value: "watching", label: "while watching" },
  { value: "always", label: "always" },
  { value: "never", label: "never" },
];
const minutes = computed(() => TOURS.reduce((n, t) => n + t.minutes, 0));
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Guide</h1>
      <p class="muted">
        {{ TOURS.length }} short walkthroughs of what Quarry can do, about {{ minutes }} minutes in all. Watch one play
        itself, then try it, each step waiting for you. Every walkthrough runs in a sandbox: a fresh copy of the demo
        world, made when it starts. Your own worlds are never touched.
      </p>
    </div>
  </div>

  <div v-if="guide.preparing" class="notice" role="status" data-testid="guide-preparing">Making a fresh copy of the demo world…</div>
  <div v-if="guide.error" class="notice error" role="alert">{{ guide.error }}</div>
  <div v-if="resumable && !guide.active" class="notice accent" data-testid="guide-resume">
    You were at step {{ resumable.step }} of “{{ resumable.title }}”.
    <button type="button" class="linkish" @click="guide.resume()">Carry on</button>
  </div>
  <div v-if="sandbox && !guide.active" class="notice small" data-testid="guide-sandbox">
    The sandbox from your last walkthrough is still there, as it was left.
    <RouterLink :to="{ name: 'world', params: { world: sandbox.slug } }">Open it</RouterLink> ·
    <button type="button" class="linkish" data-testid="guide-delete-sandbox" @click="guide.clear()">Delete it</button>
  </div>

  <div class="guide-settings small muted">
    <label for="guide-spotlight">Dim the page around what a step points at</label>
    <select
      id="guide-spotlight"
      class="filter"
      data-testid="guide-spotlight"
      :value="guide.spotlight"
      @change="guide.setSpotlight(($event.target as HTMLSelectElement).value as Spotlight)"
    >
      <option v-for="o in SPOTLIGHT" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
  </div>

  <ul class="guide-list">
    <li v-for="(t, i) in TOURS" :key="t.id" class="card guide-tour" :data-testid="`guide-tour-${t.id}`">
      <div class="card-head">
        <span class="muted small guide-no">{{ i + 1 }}</span>
        <h3 class="grow">{{ t.title }}</h3>
        <span v-if="doneOn(t.id)" class="pill ok small">Seen {{ doneOn(t.id) }}</span>
        <span class="muted small">{{ t.minutes }} min</span>
      </div>
      <p class="muted">{{ t.blurb }}</p>
      <div class="chips">
        <span v-for="c in t.covers" :key="c" class="chip static">{{ c }}</span>
      </div>
      <div class="actions">
        <button type="button" class="btn btn-sm btn-primary" :disabled="guide.preparing" data-testid="guide-watch" @click="guide.start(t.id, 'watch')">Watch</button>
        <button type="button" class="btn btn-sm" :disabled="guide.preparing" data-testid="guide-try" @click="guide.start(t.id, 'try')">Try it yourself</button>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.guide-settings {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.guide-settings select {
  width: auto;
}
.guide-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
}
.guide-tour {
  display: flex;
  flex-direction: column;
}
.guide-tour p {
  margin: 4px 0 10px;
}
.guide-tour .actions {
  margin-top: auto;
  padding-top: 12px;
}
.guide-no {
  min-width: 1.2em;
}
</style>
