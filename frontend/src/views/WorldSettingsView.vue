<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { del, patch } from "../api";
import InlineText from "../components/InlineText.vue";
import { exportUrl } from "../manuscript";
import { useSession } from "../stores/session";
import type { World } from "../types";
import NotFoundView from "./NotFoundView.vue";

// A world's settings (docs/SPEC.md §14.4): its name and address, what in-world time is counted in, and deleting it.
// Moved here from the world page, which is the front page now.

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
    if (w.slug !== old) await router.replace({ name: "world-settings", params: { world: w.slug } });
  } catch (e) {
    editError.value = (e as Error).message;
  }
}

// what in-world time is counted in (docs/SPEC.md §13.1.1): the words only, numbers are left as they are
async function setUnit(field: "time_unit" | "time_units", value: string) {
  const w = world.value;
  if (!w || !value.trim()) return;
  try {
    session.putWorld(await patch<World>(`/api/worlds/${w.slug}`, { [field]: value.trim() }));
  } catch (e) {
    editError.value = (e as Error).message;
  }
}

// deleting the whole world: only its owner, and only by typing its name
const deleting = ref(false);
const deleteName = ref("");
const deleteError = ref("");
async function deleteWorld() {
  const w = world.value;
  if (!w) return;
  deleteError.value = "";
  try {
    await del(`/api/worlds/${encodeURIComponent(w.slug)}`, { name: deleteName.value });
    session.dropWorld(w.slug);
    await router.push({ name: "home" });
  } catch (e) {
    deleteError.value = (e as Error).message;
  }
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs"><RouterLink :to="{ name: 'world', params: { world: world.slug } }">{{ world.name }}</RouterLink></div>
        <h1>World settings</h1>
      </div>
      <div class="actions">
        <button v-if="!editing" type="button" class="btn btn-sm" @click="startEdit">Rename</button>
      </div>
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

    <section class="card time-unit" data-testid="time-unit">
      <p class="small">
        Time is counted in
        <InlineText :value="world.time_unit ?? 'year'" label="One unit of time" :maxlength="40" @save="(v) => setUnit('time_unit', v)" />
        /
        <InlineText :value="world.time_units ?? 'years'" label="Several units of time" :maxlength="40" @save="(v) => setUnit('time_units', v)" />
        <span class="muted"> · chapters and history are set in numbers of these (year 312, year −800); nothing is converted.</span>
      </p>
    </section>

    <section v-if="world.role === 'owner'" class="card danger" data-testid="delete-world">
      <button v-if="!deleting" type="button" class="linkish small" @click="deleting = true">Delete this world…</button>
      <form v-else class="form" @submit.prevent="deleteWorld">
        <p class="small">
          This deletes <strong>{{ world.name }}</strong> with all its projects, chapters, history, bible and planning.
          It can't be undone. <a :href="exportUrl(world.slug)" download>Export it first</a> if you might want it back.
        </p>
        <div class="field">
          <label for="delete-name">Type the world's name to delete it</label>
          <input id="delete-name" v-model="deleteName" type="text" autocomplete="off" />
        </div>
        <div v-if="deleteError" class="notice error" role="alert">{{ deleteError }}</div>
        <div class="actions">
          <button class="btn btn-danger" type="submit" :disabled="deleteName.trim() !== world.name">Delete forever</button>
          <button class="btn" type="button" @click="(deleting = false), (deleteName = '')">Cancel</button>
        </div>
      </form>
    </section>
  </template>
</template>
