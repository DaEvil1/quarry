<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { entityNames } from "../bible";
import EntityPicker from "../components/EntityPicker.vue";
import { isPhone, readCaptureDefaults, readLastUsed, writeCaptureDefaults } from "../lastUsed";
import { useOutbox } from "../stores/outbox";
import { useSession } from "../stores/session";
import { CAPTURE_KINDS, type EntityRef } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();
const outbox = useOutbox();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));

const body = ref("");
const kind = ref<"spark" | "question" | "task">("spark");
const project = ref<string | null>(null);
const source = ref("desk");
const saving = ref(false);
const message = ref("");
const box = ref<HTMLTextAreaElement | null>(null);
// what it's about: names from the bible (the list on this device when offline)
const tags = ref<EntityRef[]>([]);
const names = ref<EntityRef[]>([]);
const tagging = ref(false);
const picker = ref<InstanceType<typeof EntityPicker> | null>(null);

async function startTag() {
  tagging.value = true;
  await nextTick();
  picker.value?.focus();
}

function addTag(e: EntityRef) {
  if (!tags.value.some((t) => t.id === e.id)) tags.value.push(e);
  tagging.value = false;
  box.value?.focus();
}

function setDefaults() {
  const saved = readCaptureDefaults(worldSlug.value);
  const last = readLastUsed();
  const fallback = last.world === worldSlug.value ? (last.project ?? null) : null;
  const wanted = saved ? saved.project : fallback;
  project.value = wanted && session.project(worldSlug.value, wanted) ? wanted : null;
  kind.value = saved?.kind ?? "spark";
}

function takeQuery() {
  const text = route.query.text;
  if (typeof text === "string" && text) {
    body.value = text;
    source.value = route.query.source === "share" ? "share" : isPhone() ? "phone" : "desk";
    // keep the shared text out of the address, so reloading doesn't capture it twice
    void router.replace({ name: "capture", params: { world: worldSlug.value } });
  } else if (!body.value) {
    source.value = isPhone() ? "phone" : "desk";
  }
}

onMounted(async () => {
  setDefaults();
  takeQuery();
  void entityNames(worldSlug.value).then((n) => (names.value = n));
  await nextTick();
  box.value?.focus();
});
watch(worldSlug, () => {
  setDefaults();
  tags.value = [];
  void entityNames(worldSlug.value).then((n) => (names.value = n));
});

const pendingHere = computed(() => outbox.forWorld(worldSlug.value));

async function save() {
  const text = body.value.trim();
  if (!text || saving.value) return;
  saving.value = true;
  message.value = "";
  writeCaptureDefaults(worldSlug.value, { project: project.value, kind: kind.value });
  try {
    const sent = await outbox.add({ world: worldSlug.value, body: text, kind: kind.value, project: project.value,
                                    source: source.value, entities: tags.value.map((t) => t.id) });
    message.value = sent ? "Saved." : "Saved on this device. It goes to the inbox when you're back online.";
    body.value = "";
    tags.value = [];
    source.value = isPhone() ? "phone" : "desk";
    if (sent) void session.refreshCounts(worldSlug.value);
  } catch (e) {
    message.value = `Could not save: ${(e as Error).message}`;
  } finally {
    saving.value = false;
    box.value?.focus();
  }
}

function onKey(e: KeyboardEvent) {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    void save();
  }
}
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <form v-else class="capture" @submit.prevent="save">
    <label for="capture-body" class="visually-hidden">What's on your mind?</label>
    <textarea
      id="capture-body"
      ref="box"
      v-model="body"
      class="capture-box"
      placeholder="What's on your mind?"
      rows="7"
      @keydown="onKey"
    />

    <div class="chips" role="radiogroup" aria-label="Kind">
      <button
        v-for="k in CAPTURE_KINDS"
        :key="k.value"
        type="button"
        role="radio"
        class="chip"
        :aria-checked="kind === k.value"
        @click="kind = k.value"
      >
        {{ k.label }}
      </button>
    </div>

    <div class="chips" role="radiogroup" aria-label="Belongs to">
      <button type="button" role="radio" class="chip" :aria-checked="project === null" @click="project = null">
        Whole world
      </button>
      <button
        v-for="p in world.projects"
        :key="p.id"
        type="button"
        role="radio"
        class="chip"
        :aria-checked="project === p.slug"
        @click="project = p.slug"
      >
        {{ p.name }}
      </button>
    </div>

    <div class="chips" aria-label="About">
      <span v-for="t in tags" :key="t.id" class="chip static tag">
        {{ t.name }}
        <button type="button" class="chip-x" :aria-label="`Remove ${t.name}`" @click="tags = tags.filter((x) => x.id !== t.id)">×</button>
      </span>
      <button v-if="!tagging" type="button" class="chip" @click="startTag">+ Tag</button>
    </div>
    <EntityPicker
      v-if="tagging"
      ref="picker"
      :entities="names"
      :exclude="tags.map((t) => t.id)"
      @pick="addTag"
      @cancel="tagging = false"
    />

    <div class="actions">
      <button class="btn btn-primary capture-save" type="submit" :disabled="saving || !body.trim()">Save</button>
      <span class="muted small desk-only">Ctrl+Enter</span>
      <span v-if="message" class="small" role="status" data-testid="capture-status">{{ message }}</span>
    </div>

    <div v-if="pendingHere.length" class="notice" data-testid="pending">
      <strong>{{ pendingHere.length }} waiting to sync</strong>
      <span class="muted"> · saved on this device</span>
      <ul class="rows">
        <li v-for="p in pendingHere" :key="p.id">
          <span class="grow">{{ p.body.split("\n", 1)[0] }}</span>
          <template v-if="p.error">
            <span class="pill warn" :title="p.error">Refused</span>
            <button type="button" class="btn btn-sm" @click="outbox.retry(p.id, { project: null })">
              Save to whole world
            </button>
            <button type="button" class="btn btn-sm" @click="outbox.discard(p.id)">Discard</button>
          </template>
        </li>
      </ul>
    </div>
  </form>
</template>
