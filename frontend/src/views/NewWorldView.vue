<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { get, post } from "../api";
import { restoreWorld } from "../manuscript";
import { useSession } from "../stores/session";
import { PROJECT_KINDS, type Project, type ProjectKind, type World } from "../types";

const router = useRouter();
const session = useSession();

const first = computed(() => session.worlds.length === 0);
const name = ref("");
const projectName = ref("");
const kind = ref<ProjectKind>("novel");
const busy = ref(false);
const error = ref("");

// or: a world from an export zip
const restoring = ref(false);
async function restore(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  error.value = "";
  restoring.value = true;
  try {
    const world = await restoreWorld(file);
    session.putWorld(world);
    await router.push({ name: "world", params: { world: world.slug } });
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    restoring.value = false;
  }
}

// or: the demo world, a made-up story that uses every part of Quarry
const loadingDemo = ref(false);
async function demo() {
  error.value = "";
  loadingDemo.value = true;
  try {
    const world = await post<World>("/api/worlds/demo");
    session.putWorld(world);
    await router.push({ name: "world", params: { world: world.slug } });
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loadingDemo.value = false;
  }
}

async function create() {
  error.value = "";
  busy.value = true;
  try {
    let world = await post<World>("/api/worlds", { name: name.value });
    let project: Project | undefined;
    if (projectName.value.trim()) {
      project = await post<Project>(`/api/worlds/${world.slug}/projects`, { name: projectName.value, kind: kind.value });
      world = await get<World>(`/api/worlds/${world.slug}`);
    }
    session.putWorld(world);
    await router.push(
      project
        ? { name: "project", params: { world: world.slug, project: project.slug } }
        : { name: "world", params: { world: world.slug } },
    );
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>{{ first ? "Create your first world" : "New world" }}</h1>
      <p class="muted">
        A world is a shared setting. It holds the bible, and any number of projects (novels, novellas, stories) set in
        it.
      </p>
    </div>
  </div>
  <form class="card form" @submit.prevent="create">
    <div class="field">
      <label for="world-name">World name</label>
      <input id="world-name" v-model="name" type="text" maxlength="200" required />
    </div>
    <div class="field">
      <label for="project-name">First project <span class="muted">(optional)</span></label>
      <input id="project-name" v-model="projectName" type="text" maxlength="200" />
    </div>
    <div v-if="projectName.trim()" class="field">
      <label for="project-kind">Kind</label>
      <select id="project-kind" v-model="kind">
        <option v-for="k in PROJECT_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
      </select>
    </div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <div class="actions">
      <button class="btn btn-primary" type="submit" :disabled="busy">Create world</button>
    </div>
  </form>

  <section class="card form" data-testid="demo-world">
    <h2>Or look around a demo world</h2>
    <p class="muted small">
      <em>The Ninefold Delta</em>: a short made-up story in two books, with a bible, relationships, places, an inbox, a
      journal and decisions, and a few planted slips for the writing companion to find. It is a world of its own; delete
      it whenever you like.
    </p>
    <div class="actions">
      <button class="btn" type="button" :disabled="loadingDemo" @click="demo">{{ loadingDemo ? "Loading…" : "Load the demo world" }}</button>
    </div>
  </section>

  <section class="card form">
    <h2>Or restore a world</h2>
    <p class="muted small">From a zip made with Export. It becomes a new world; nothing existing is changed.</p>
    <div class="field">
      <label for="restore-file">Export zip</label>
      <input id="restore-file" type="file" accept=".zip,application/zip" :disabled="restoring" @change="restore" />
    </div>
    <p v-if="restoring" class="muted small">Restoring…</p>
  </section>
</template>
