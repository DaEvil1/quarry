<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get, patch, post, put } from "../api";
import { useSession } from "../stores/session";
import { PROJECT_KINDS, kindLabel, type Project, type ProjectKind, type World } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();

const world = computed(() => session.world(String(route.params.world)));

// rename / change address
const editing = ref(false);
const editName = ref("");
const editSlug = ref("");
const editError = ref("");
watch(world, () => (editing.value = false));

function startEdit() {
  if (!world.value) return;
  editName.value = world.value.name;
  editSlug.value = world.value.slug;
  editError.value = "";
  editing.value = true;
}

async function saveEdit() {
  if (!world.value) return;
  editError.value = "";
  const old = world.value.slug;
  try {
    const w = await patch<World>(`/api/worlds/${old}`, { name: editName.value, slug: editSlug.value.trim() });
    session.putWorld(w, old);
    editing.value = false;
    if (w.slug !== old) await router.replace({ name: "world", params: { world: w.slug } });
  } catch (e) {
    editError.value = (e as Error).message;
  }
}

// new project
const newName = ref("");
const newKind = ref<ProjectKind>("novel");
const newError = ref("");
const busy = ref(false);

async function refresh(slug: string) {
  session.putWorld(await get<World>(`/api/worlds/${slug}`));
}

async function addProject() {
  if (!world.value) return;
  newError.value = "";
  busy.value = true;
  try {
    await post<Project>(`/api/worlds/${world.value.slug}/projects`, { name: newName.value, kind: newKind.value });
    await refresh(world.value.slug);
    newName.value = "";
  } catch (e) {
    newError.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}

async function move(index: number, by: -1 | 1) {
  const w = world.value;
  if (!w) return;
  const ids = w.projects.map((p) => p.id);
  const [id] = ids.splice(index, 1);
  ids.splice(index + by, 0, id);
  await put(`/api/worlds/${w.slug}/project-order`, { ids });
  await refresh(w.slug);
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">World</div>
        <h1>{{ world.name }}</h1>
      </div>
      <button v-if="!editing" type="button" class="btn btn-sm" @click="startEdit">Rename</button>
    </div>

    <form v-if="editing" class="card form" @submit.prevent="saveEdit">
      <div class="field">
        <label for="w-name">Name</label>
        <input id="w-name" v-model="editName" type="text" maxlength="200" required />
      </div>
      <div class="field">
        <label for="w-slug">Address</label>
        <input id="w-slug" v-model="editSlug" type="text" maxlength="60" spellcheck="false" required />
        <div class="hint">Shown in links as /w/{{ editSlug || "…" }}. Lowercase letters, digits and hyphens.</div>
      </div>
      <div v-if="editError" class="notice error" role="alert">{{ editError }}</div>
      <div class="actions">
        <button class="btn btn-primary" type="submit">Save</button>
        <button class="btn" type="button" @click="editing = false">Cancel</button>
      </div>
    </form>

    <section class="card">
      <div class="card-head"><h2>Projects</h2></div>
      <ul v-if="world.projects.length" class="rows">
        <li v-for="(p, i) in world.projects" :key="p.id">
          <RouterLink class="grow" :to="{ name: 'project', params: { world: world.slug, project: p.slug } }">{{
            p.name
          }}</RouterLink>
          <span class="pill">{{ kindLabel(p.kind) }}</span>
          <button
            type="button"
            class="icon-btn"
            :disabled="i === 0"
            :aria-label="`Move ${p.name} up`"
            @click="move(i, -1)"
          >
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M3 10l5-5 5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <button
            type="button"
            class="icon-btn"
            :disabled="i === world.projects.length - 1"
            :aria-label="`Move ${p.name} down`"
            @click="move(i, 1)"
          >
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </li>
      </ul>
      <p v-else class="empty">No projects in this world yet.</p>
    </section>

    <form class="card form" @submit.prevent="addProject">
      <h2>New project</h2>
      <div class="field">
        <label for="p-name">Name</label>
        <input id="p-name" v-model="newName" type="text" maxlength="200" required />
      </div>
      <div class="field">
        <label for="p-kind">Kind</label>
        <select id="p-kind" v-model="newKind">
          <option v-for="k in PROJECT_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
      </div>
      <div v-if="newError" class="notice error" role="alert">{{ newError }}</div>
      <div class="actions">
        <button class="btn btn-primary" type="submit" :disabled="busy">Add project</button>
      </div>
    </form>
  </template>
</template>
