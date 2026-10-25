<script setup lang="ts">
// The Guide (docs/SPEC.md §15): short walkthroughs of what Quarry does, each on a fresh sandbox copy of the demo
// world. Watch one play itself, or try it with each step waiting for you. Nothing here runs unless asked.
import { computed } from "vue";

import { LATER, TOURS } from "../guide/tours";
import { useGuide } from "../stores/guide";
import { useSession } from "../stores/session";

const guide = useGuide();
const session = useSession();
const leftover = computed(() => !guide.active && session.worlds.some((w) => w.sandbox));
const doneOn = (id: string) => {
  const at = guide.done[id];
  return at ? new Date(at).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "";
};
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Guide</h1>
      <p class="muted">
        Short walkthroughs of what Quarry can do, each a few minutes. Every walkthrough runs in a sandbox: a fresh copy
        of the demo world, made when it starts and deleted when it ends. Your own worlds are never touched.
      </p>
    </div>
  </div>

  <div v-if="guide.preparing" class="notice" role="status" data-testid="guide-preparing">Making a fresh copy of the demo world…</div>
  <div v-if="guide.error" class="notice error" role="alert">{{ guide.error }}</div>
  <div v-if="leftover" class="notice warn" data-testid="guide-leftover">
    A sandbox from an earlier walkthrough is still there.
    <button type="button" class="linkish" @click="guide.clear()">Delete it</button>
  </div>

  <ul class="guide-list">
    <li v-for="t in TOURS" :key="t.id" class="card guide-tour" :data-testid="`guide-tour-${t.id}`">
      <div class="card-head">
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

  <h2 class="guide-later-head">Still to write</h2>
  <ul class="rows guide-later">
    <li v-for="l in LATER" :key="l.title">
      <strong>{{ l.title }}</strong> <span class="muted small">· {{ l.covers }}</span>
    </li>
  </ul>
</template>

<style scoped>
.guide-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
}
.guide-tour p {
  margin: 4px 0 10px;
}
.guide-tour .actions {
  margin-top: 12px;
}
.guide-later-head {
  margin-top: 28px;
  font-size: 1rem;
}
.guide-later li {
  padding: 6px 0;
}
</style>
