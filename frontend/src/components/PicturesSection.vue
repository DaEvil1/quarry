<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  countText,
  deletePicture,
  listPictures,
  NEEDS_NETWORK,
  pictureUrl,
  renamePicture,
  sizeText,
  uploadPicture,
  type Picture,
  type PictureUses,
} from "../pictures";
import { useViewer } from "../stores/viewer";
import { useCards } from "../world/cards";
import UndoToast from "./UndoToast.vue";

// The Pictures page, a section of World settings (docs/SPEC.md §17.1): every picture in the world, newest first, with
// its size and where it is used. Rename (Undo on the toast); Delete only for a picture used nowhere, asking first.
const props = defineProps<{ world: string }>();
const cards = useCards();
const viewer = useViewer();

type Row = Picture & { uses: PictureUses };
const rows = ref<Row[] | null>(null);
const total = ref({ count: 0, bytes: 0 });
const error = ref("");
const uploads = ref<{ key: number; name: string; error?: string }[]>([]);
const renaming = ref<string | null>(null);
const newName = ref("");
const toast = ref<{ label: string; undo: (() => Promise<void>) | null } | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
let key = 0;

async function load() {
  try {
    const out = await listPictures(props.world);
    rows.value = out.pictures;
    total.value = { count: out.count, bytes: out.bytes };
    error.value = "";
  } catch (e) {
    rows.value = rows.value ?? [];
    error.value = navigator.onLine === false ? NEEDS_NETWORK : (e as Error).message;
  }
}
onMounted(load);

function upload() {
  if (navigator.onLine === false) {
    error.value = NEEDS_NETWORK;
    return;
  }
  fileInput.value?.click();
}
async function chosen(e: Event) {
  const files = [...((e.target as HTMLInputElement).files ?? [])];
  (e.target as HTMLInputElement).value = "";
  for (const file of files) {
    const line = { key: ++key, name: file.name || "picture" };
    uploads.value = [...uploads.value, line];
    try {
      cards.putPicture(await uploadPicture(props.world, file));
      uploads.value = uploads.value.filter((u) => u.key !== line.key);
      await load();
    } catch (err) {
      uploads.value = uploads.value.map((u) => (u.key === line.key ? { ...u, error: (err as Error).message } : u));
    }
  }
}

async function rename(p: Row) {
  const name = newName.value.trim();
  renaming.value = null;
  if (!name || name === p.name) return;
  const old = p.name;
  try {
    cards.putPicture(await renamePicture(p.id, name));
    await load();
    toast.value = {
      label: `Renamed to ${name}`,
      undo: async () => {
        cards.putPicture(await renamePicture(p.id, old));
        await load();
      },
    };
  } catch (e) {
    error.value = (e as Error).message;
  }
}
async function remove(p: Row) {
  if (!confirm(`Delete ${p.name}? This can't be undone.`)) return;
  try {
    await deletePicture(p.id);
    await load();
    void cards.refresh(props.world);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
const used = (p: Row) => p.uses.entities.length + p.uses.texts.length > 0;
const TABLE: Record<string, string> = { chapter: "chapter", journal: "Journal", entity: "notes of", cut: "cuts bin" };
function textLink(t: PictureUses["texts"][number]) {
  if (t.table === "chapter") return { name: "chapter", params: { world: props.world, id: t.id } };
  if (t.table === "journal") return { name: "journal-entry", params: { world: props.world, id: t.id } };
  if (t.table === "entity") return { name: "entity", params: { world: props.world, id: t.id } };
  return t.project ? { name: "salvage", params: { world: props.world, project: t.project } } : { name: "world", params: { world: props.world } };
}
</script>

<template>
  <section class="card pictures-page" data-testid="pictures-page">
    <div class="card-head">
      <h2>Pictures</h2>
      <span class="muted small" data-testid="pictures-total">{{ countText(total.count) }} · {{ sizeText(total.bytes) }}</span>
      <button type="button" class="btn btn-sm" data-testid="pictures-upload" @click="upload">Upload…</button>
      <input ref="fileInput" type="file" accept="image/*" multiple hidden data-testid="pictures-file" @change="chosen" />
    </div>
    <ul v-if="uploads.length" class="plain-list small">
      <li v-for="u in uploads" :key="u.key" :class="{ 'error-text': u.error }">{{ u.error ? `${u.name}: ${u.error}` : `Uploading ${u.name}…` }}</li>
    </ul>
    <div v-if="error" class="notice error small" role="alert" data-testid="pictures-error">{{ error }}</div>
    <p v-if="rows && !rows.length" class="empty">No pictures yet. Add them on an entry's page, paste them into a chapter, or upload them here.</p>
    <ul v-else-if="rows" class="rows picture-rows">
      <li v-for="p in rows" :key="p.id" :data-picture="p.id" data-testid="picture-row">
        <button type="button" class="picture-row-thumb" :aria-label="`Open ${p.name}`" @click="viewer.show([{ id: p.id, name: p.name, caption: '' }])">
          <img :src="pictureUrl(p.id, 'thumb')" :alt="p.name" loading="lazy" />
        </button>
        <div class="grow">
          <form v-if="renaming === p.id" class="actions" @submit.prevent="rename(p)">
            <input v-model="newName" class="filter" type="text" maxlength="200" aria-label="Name" @keydown.esc="renaming = null" />
            <button class="btn btn-sm btn-primary" type="submit">Save</button>
          </form>
          <strong v-else data-testid="picture-name">{{ p.name }}</strong>
          <span class="muted small"> · {{ p.width }} × {{ p.height }} · {{ sizeText(p.size) }}</span>
          <div class="small" data-testid="picture-uses">
            <template v-if="used(p)">
              <span class="muted">Used in </span>
              <template v-for="(e, i) in p.uses.entities" :key="e.id"><template v-if="i">, </template><RouterLink :to="{ name: 'entity', params: { world, id: e.id } }" :class="`k-${e.kind}`">{{ e.name }}</RouterLink></template>
              <template v-for="(t, i) in p.uses.texts" :key="t.table + t.id"><template v-if="i || p.uses.entities.length">, </template><span class="muted">{{ `${TABLE[t.table]} ` }}</span><RouterLink :to="textLink(t)">{{ t.title }}</RouterLink></template>
            </template>
            <span v-else class="muted">Used nowhere</span>
          </div>
        </div>
        <span class="actions">
          <button type="button" class="btn btn-sm" data-testid="picture-rename" @click="(renaming = p.id), (newName = p.name)">Rename</button>
          <button v-if="!used(p)" type="button" class="btn btn-sm" data-testid="picture-delete" @click="remove(p)">Delete</button>
        </span>
      </li>
    </ul>
    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" @dismiss="toast = null" />
  </section>
</template>
