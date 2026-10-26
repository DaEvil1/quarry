<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";

import { countText, listPictures, NEEDS_NETWORK, pictureUrl, type Picture, type PictureUses } from "../pictures";

// Choosing one of the world's pictures (docs/SPEC.md §17.2, §17.3): "From the world…" on an entry, "Picture…" in the
// editor. Type to filter by name or by any of a picture's captions; the pictures of entries named in the text come
// first. With `upload`, it also offers Upload….
const props = defineProps<{ world: string; named?: string[]; upload?: boolean; exclude?: string[]; title?: string }>();
const emit = defineEmits<{ pick: [picture: Picture]; files: [files: File[]]; close: [] }>();

const all = ref<(Picture & { uses: PictureUses })[] | null>(null);
const error = ref("");
const filter = ref("");
const box = ref<HTMLInputElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

onMounted(async () => {
  await nextTick();
  box.value?.focus();
  try {
    all.value = (await listPictures(props.world)).pictures;
  } catch (e) {
    all.value = [];
    error.value = navigator.onLine === false ? NEEDS_NETWORK : (e as Error).message;
  }
});

const shown = computed(() => {
  const q = filter.value.trim().toLowerCase();
  const named = new Set(props.named ?? []);
  const skip = new Set(props.exclude ?? []);
  const list = (all.value ?? []).filter((p) => !skip.has(p.id) && (!q || p.name.toLowerCase().includes(q) || p.uses.captions.some((c) => c.toLowerCase().includes(q))));
  const near = (p: (typeof list)[number]) => (p.uses.entities.some((e) => named.has(e.id)) ? 0 : 1);
  return [...list].sort((a, b) => near(a) - near(b));
});

function chosen(e: Event) {
  const files = [...((e.target as HTMLInputElement).files ?? [])];
  (e.target as HTMLInputElement).value = "";
  if (files.length) emit("files", files);
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") emit("close");
  if (e.key === "Enter" && shown.value[0]) {
    e.preventDefault();
    emit("pick", shown.value[0]);
  }
}
</script>

<template>
  <div class="picker-overlay" role="dialog" aria-modal="true" :aria-label="title ?? 'Pictures'" data-testid="picture-picker" @click.self="emit('close')">
    <div class="card picker">
      <div class="card-head">
        <h2>{{ title ?? "Pictures" }}</h2>
        <span v-if="all" class="muted small">{{ countText(all.length) }}</span>
        <button type="button" class="btn btn-sm" aria-label="Close" @click="emit('close')">×</button>
      </div>
      <div class="actions">
        <input ref="box" v-model="filter" class="filter grow" type="search" placeholder="Filter by name or caption" aria-label="Filter pictures" @keydown="onKey" />
        <template v-if="upload">
          <button type="button" class="btn btn-sm" data-testid="picker-upload" @click="fileInput?.click()">Upload…</button>
          <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden @change="chosen" />
        </template>
      </div>
      <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
      <p v-if="all === null" class="muted small">Loading…</p>
      <p v-else-if="!shown.length" class="empty">{{ all.length ? "No picture matches." : "No pictures in this world yet." }}</p>
      <ul v-else class="picker-grid">
        <li v-for="p in shown" :key="p.id">
          <button type="button" class="picker-thumb" :title="p.name" :data-picture="p.id" data-testid="picker-thumb" @click="emit('pick', p)">
            <img :src="pictureUrl(p.id, 'thumb')" :alt="p.name" loading="lazy" />
            <span class="small">{{ p.name }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>
