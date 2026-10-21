<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get, patch } from "../api";
import { age, listItems } from "../items";
import { useSession } from "../stores/session";
import { PROJECT_KINDS, firstLine, kindLabel, type Item, type Project, type ProjectKind, type World } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();

const world = computed(() => session.world(String(route.params.world)));
const project = computed(() =>
  world.value ? session.project(world.value.slug, String(route.params.project)) : undefined,
);

const openItems = ref<Item[]>([]);
watch(
  project,
  async (p) => {
    openItems.value = [];
    if (!p || !world.value) return;
    try {
      openItems.value = await listItems(world.value.slug, { project: p.slug, limit: 20 });
    } catch {
      /* offline: the list fills in when back */
    }
  },
  { immediate: true },
);

const editing = ref(false);
const name = ref("");
const slug = ref("");
const kind = ref<ProjectKind>("novel");
const error = ref("");
watch(project, () => (editing.value = false));

function startEdit() {
  if (!project.value) return;
  name.value = project.value.name;
  slug.value = project.value.slug;
  kind.value = project.value.kind;
  error.value = "";
  editing.value = true;
}

async function save() {
  const w = world.value;
  const p = project.value;
  if (!w || !p) return;
  error.value = "";
  try {
    const updated = await patch<Project>(`/api/worlds/${w.slug}/projects/${p.slug}`, {
      name: name.value,
      slug: slug.value.trim(),
      kind: kind.value,
    });
    session.putWorld(await get<World>(`/api/worlds/${w.slug}`));
    editing.value = false;
    if (updated.slug !== p.slug) {
      await router.replace({ name: "project", params: { world: w.slug, project: updated.slug } });
    }
  } catch (e) {
    error.value = (e as Error).message;
  }
}
</script>

<template>
  <NotFoundView v-if="!world || !project" what="project" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'world', params: { world: world.slug } }">{{ world.name }}</RouterLink>
          · {{ kindLabel(project.kind) }}
        </div>
        <h1>{{ project.name }}</h1>
      </div>
      <button v-if="!editing" type="button" class="btn btn-sm" @click="startEdit">Edit</button>
    </div>

    <form v-if="editing" class="card form" @submit.prevent="save">
      <div class="field">
        <label for="p-name">Name</label>
        <input id="p-name" v-model="name" type="text" maxlength="200" required />
      </div>
      <div class="field">
        <label for="p-kind">Kind</label>
        <select id="p-kind" v-model="kind">
          <option v-for="k in PROJECT_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
      </div>
      <div class="field">
        <label for="p-slug">Address</label>
        <input id="p-slug" v-model="slug" type="text" maxlength="60" spellcheck="false" required />
        <div class="hint">Shown in links as /w/{{ world.slug }}/p/{{ slug || "…" }}.</div>
      </div>
      <div v-if="error" class="notice error" role="alert">{{ error }}</div>
      <div class="actions">
        <button class="btn btn-primary" type="submit">Save</button>
        <button class="btn" type="button" @click="editing = false">Cancel</button>
      </div>
    </form>

    <section class="card">
      <div class="card-head">
        <h2>Open items</h2>
        <div class="actions">
          <RouterLink class="btn btn-sm" :to="{ name: 'triage', params: { world: world.slug }, query: { project: project.slug } }">
            Triage
          </RouterLink>
          <RouterLink :to="{ name: 'inbox', params: { world: world.slug }, query: { project: project.slug } }">
            Inbox
          </RouterLink>
        </div>
      </div>
      <ul v-if="openItems.length" class="rows">
        <li v-for="i in openItems" :key="i.id">
          <span class="pill" :class="`kind-${i.kind}`">{{ i.kind }}</span>
          <span class="grow">{{ firstLine(i) }}</span>
          <span class="muted small">{{ age(i.created_at) }}</span>
        </li>
      </ul>
      <p v-else class="empty">Nothing open for this project.</p>
    </section>

    <section class="card">
      <div class="card-head"><h2>Manuscript</h2></div>
      <p class="empty">No chapters yet. The editor arrives in phase 4.</p>
    </section>
  </template>
</template>
