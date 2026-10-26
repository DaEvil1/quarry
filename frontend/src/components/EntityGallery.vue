<script setup lang="ts">
import { ref } from "vue";

import { NEEDS_NETWORK, pictureUrl, setGallery, uploadPicture, type GalleryPicture, type Picture } from "../pictures";
import { useViewer } from "../stores/viewer";
import { useCards } from "../world/cards";
import PicturePicker from "./PicturePicker.vue";
import UndoToast from "./UndoToast.vue";

// An entry's gallery (docs/SPEC.md §17.2): any number of pictures in an order, each with an optional caption; the first
// is the entry's main picture. Changes are saved at once and aren't revisions; each has Undo on its toast.
const props = defineProps<{ world: string; entityId: string; entityName: string; pictures: GalleryPicture[] }>();
const emit = defineEmits<{ changed: [gallery: GalleryPicture[]] }>();
const cards = useCards();
const viewer = useViewer();

const fileInput = ref<HTMLInputElement | null>(null);
const uploads = ref<{ key: number; name: string; error?: string }[]>([]);
const picking = ref(false);
const menu = ref<string | null>(null);
const captioning = ref<string | null>(null);
const captionText = ref("");
const error = ref("");
const toast = ref<{ label: string; undo: (() => Promise<void>) | null } | null>(null);
const dropping = ref(false);
let key = 0;

const order = (list: GalleryPicture[]) => list.map((g) => ({ picture: g.id, caption: g.caption }));

async function save(next: { picture: string; caption: string }[], label?: string) {
  const before = order(props.pictures);
  error.value = "";
  try {
    const out = await setGallery(props.world, props.entityId, next);
    emit("changed", out);
    void cards.refresh(props.world);
    if (label) {
      toast.value = {
        label,
        undo: async () => {
          emit("changed", await setGallery(props.world, props.entityId, before));
          void cards.refresh(props.world);
        },
      };
    }
  } catch (e) {
    error.value = navigator.onLine === false ? NEEDS_NETWORK : (e as Error).message;
  }
}

/** Each file gets its own progress line; the pictures join the end of the gallery as they arrive. */
async function add(files: File[]) {
  if (navigator.onLine === false) {
    error.value = NEEDS_NETWORK;
    return;
  }
  for (const file of files) {
    const line = { key: ++key, name: file.name || "picture" };
    uploads.value = [...uploads.value, line];
    try {
      const p = await uploadPicture(props.world, file);
      cards.putPicture(p);
      uploads.value = uploads.value.filter((u) => u.key !== line.key);
      await save([...order(props.pictures), { picture: p.id, caption: "" }]);
    } catch (e) {
      uploads.value = uploads.value.map((u) => (u.key === line.key ? { ...u, error: (e as Error).message } : u));
    }
  }
}
function chosen(e: Event) {
  const files = [...((e.target as HTMLInputElement).files ?? [])];
  (e.target as HTMLInputElement).value = "";
  if (files.length) void add(files);
}
function dropped(e: DragEvent) {
  dropping.value = false;
  const files = [...(e.dataTransfer?.files ?? [])];
  if (files.length) void add(files);
}
function fromWorld(p: Picture) {
  picking.value = false;
  void save([...order(props.pictures), { picture: p.id, caption: "" }]);
}

function makeMain(id: string) {
  menu.value = null;
  const list = order(props.pictures);
  const at = list.findIndex((g) => g.picture === id);
  if (at > 0) void save([list[at]!, ...list.filter((_, i) => i !== at)], "Made the main picture");
}
function remove(id: string) {
  menu.value = null;
  const name = props.pictures.find((g) => g.id === id)?.name ?? "the picture";
  void save(order(props.pictures).filter((g) => g.picture !== id), `Removed ${name} from ${props.entityName}`);
}
function startCaption(g: GalleryPicture) {
  menu.value = null;
  captioning.value = g.id;
  captionText.value = g.caption;
}
function saveCaption() {
  const id = captioning.value;
  captioning.value = null;
  if (id) void save(order(props.pictures).map((g) => (g.picture === id ? { ...g, caption: captionText.value.trim() } : g)));
}
function move(id: string, by: number) {
  const list = order(props.pictures);
  const at = list.findIndex((g) => g.picture === id);
  const to = at + by;
  if (at < 0 || to < 0 || to >= list.length) return;
  [list[at], list[to]] = [list[to]!, list[at]!];
  void save(list);
}
// dragging into a new order, on the desk
const dragged = ref<string | null>(null);
function dropOn(id: string) {
  const from = dragged.value;
  dragged.value = null;
  if (!from || from === id) return;
  const list = order(props.pictures);
  const item = list.find((g) => g.picture === from)!;
  const rest = list.filter((g) => g.picture !== from);
  rest.splice(rest.findIndex((g) => g.picture === id), 0, item);
  void save(rest);
}
const open = (i: number) => viewer.show(props.pictures.map((g) => ({ id: g.id, caption: g.caption, name: g.name })), i);
</script>

<template>
  <section class="card gallery" :class="{ dropping }" data-testid="gallery" @dragover.prevent="dropping = !dragged" @dragleave="dropping = false" @drop.prevent="dragged ? null : dropped($event)">
    <div v-if="!pictures.length && !uploads.length" class="gallery-empty">
      <h2 class="inline-h">Pictures</h2> ·
      <button type="button" class="linkish" data-testid="gallery-add" @click="fileInput?.click()">Add…</button>
      <span class="muted"> or </span>
      <button type="button" class="linkish" data-testid="gallery-from-world" @click="picking = true">from the world…</button>
    </div>
    <template v-else>
      <div class="card-head">
        <h2>Pictures</h2>
        <span class="actions">
          <button type="button" class="btn btn-sm" data-testid="gallery-add" @click="fileInput?.click()">Add pictures…</button>
          <button type="button" class="btn btn-sm" data-testid="gallery-from-world" @click="picking = true">From the world…</button>
        </span>
      </div>
      <ul class="gallery-grid">
        <li v-for="(g, i) in pictures" :key="g.id" class="gallery-item" :class="{ main: i === 0 }" draggable="true" :data-picture="g.id" data-testid="gallery-item"
          @dragstart="dragged = g.id" @dragend="dragged = null" @dragover.prevent @drop.prevent.stop="dropOn(g.id)">
          <button type="button" class="gallery-thumb" :aria-label="`Open ${g.caption || g.name}`" @click="open(i)">
            <img :src="pictureUrl(g.id, 'thumb')" :alt="g.caption || g.name" loading="lazy" />
          </button>
          <form v-if="captioning === g.id" class="gallery-caption-form" @submit.prevent="saveCaption">
            <input v-model="captionText" class="filter" type="text" maxlength="2000" aria-label="Caption" placeholder="Caption" @keydown.esc="captioning = null" />
            <button class="btn btn-sm btn-primary" type="submit">Save</button>
          </form>
          <div v-else class="gallery-caption small" data-testid="gallery-caption">{{ g.caption }}<span v-if="!g.caption" class="muted">{{ g.name }}</span></div>
          <div class="gallery-tools">
            <button type="button" class="chip-x phone-arrows" :disabled="i === 0" :aria-label="`Move ${g.name} earlier`" @click="move(g.id, -1)">‹</button>
            <span class="gallery-menu-wrap">
              <button type="button" class="linkish small" aria-haspopup="menu" :aria-expanded="menu === g.id" data-testid="gallery-more" @click="menu = menu === g.id ? null : g.id">More…</button>
              <span v-if="menu === g.id" class="status-menu" role="menu">
                <button v-if="i > 0" type="button" role="menuitem" data-testid="make-main" @click="makeMain(g.id)">Make main</button>
                <button type="button" role="menuitem" data-testid="caption" @click="startCaption(g)">Caption…</button>
                <button type="button" role="menuitem" data-testid="remove-picture" @click="remove(g.id)">Remove from this entry</button>
              </span>
            </span>
            <button type="button" class="chip-x phone-arrows" :disabled="i === pictures.length - 1" :aria-label="`Move ${g.name} later`" @click="move(g.id, 1)">›</button>
          </div>
        </li>
      </ul>
    </template>
    <ul v-if="uploads.length" class="plain-list small" data-testid="uploads">
      <li v-for="u in uploads" :key="u.key" :class="{ 'error-text': u.error }">{{ u.error ? `${u.name}: ${u.error}` : `Uploading ${u.name}…` }}</li>
    </ul>
    <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
    <!-- on the phone the browser offers the camera or the gallery -->
    <input ref="fileInput" type="file" accept="image/*" multiple hidden data-testid="gallery-file" @change="chosen" />
    <PicturePicker v-if="picking" :world="world" :exclude="pictures.map((g) => g.id)" title="From the world" @pick="fromWorld" @close="picking = false" />
    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" @dismiss="toast = null" />
  </section>
</template>
