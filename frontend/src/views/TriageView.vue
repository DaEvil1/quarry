<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get } from "../api";
import { entityNames, linkItem, unlinkItem } from "../bible";
import EntityPicker from "../components/EntityPicker.vue";
import MentionText from "../components/MentionText.vue";
import ProjectFilter from "../components/ProjectFilter.vue";
import UndoToast from "../components/UndoToast.vue";
import { age, closeItem, ItemConflict, listItems, undoClose, updateItem } from "../items";
import { useSession } from "../stores/session";
import { STATUS_LABELS, type CloseStatus, type EntityRef, type Item } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const session = useSession();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const project = ref(typeof route.query.project === "string" ? route.query.project : "");
const queue = ref<Item[]>([]);
const index = ref(0);
const loading = ref(true);
const error = ref("");
const item = computed<Item | undefined>(() => queue.value[index.value]);

// closing asks for an optional line: a decision for accept and reject, a note on what to keep for harvest
const prompt = ref<CloseStatus | null>(null);
const promptText = ref("");
const promptBox = ref<HTMLInputElement | null>(null);
const editing = ref(false);
const draft = ref("");
const editBox = ref<HTMLTextAreaElement | null>(null);
const projectSelect = ref<HTMLSelectElement | null>(null);
const busy = ref(false);
const toast = ref<{ label: string; undo: () => Promise<void> } | null>(null);
const showKeys = ref(false);
const tagging = ref(false);
const names = ref<EntityRef[]>([]);
const picker = ref<InstanceType<typeof EntityPicker> | null>(null);

/** Load the current item again (after a name fix or a tag). */
async function reloadCurrent() {
  const current = item.value;
  if (!current) return;
  try {
    replace(await get<Item>(`/api/worlds/${encodeURIComponent(worldSlug.value)}/items/${current.id}`));
  } catch {
    /* keep what is shown */
  }
}

async function startTag() {
  if (!item.value) return;
  // the names first: a picker that opens empty swallows a quick "type and Enter"
  names.value = await entityNames(worldSlug.value);
  tagging.value = true;
  await nextTick();
  picker.value?.focus();
}

function tag(e: EntityRef) {
  const current = item.value;
  if (!current) return;
  return act(async () => {
    await linkItem(worldSlug.value, current.id, e.id);
    tagging.value = false;
    await reloadCurrent();
  });
}

function untag(e: EntityRef) {
  const current = item.value;
  if (!current) return;
  return act(async () => {
    await unlinkItem(worldSlug.value, current.id, e.id);
    await reloadCurrent();
  });
}

const projectName = (slug: string | null) =>
  slug ? (world.value?.projects.find((p) => p.slug === slug)?.name ?? slug) : "Whole world";

async function load() {
  if (!world.value) return;
  loading.value = true;
  error.value = "";
  try {
    queue.value = await listItems(worldSlug.value, { status: "open", order: "oldest", project: project.value || undefined });
    index.value = 0;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}
watch([worldSlug, project], load, { immediate: true });

function replace(updated: Item) {
  queue.value = queue.value.map((i) => (i.id === updated.id ? updated : i));
}

async function act(fn: () => Promise<void>) {
  busy.value = true;
  error.value = "";
  try {
    await fn();
  } catch (e) {
    if (e instanceof ItemConflict) replace(e.current);
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}

async function ask(status: CloseStatus) {
  if (!item.value) return;
  if (status === "deferred") return finish("deferred", "");
  prompt.value = status;
  promptText.value = "";
  await nextTick();
  promptBox.value?.focus();
}

function finish(status: CloseStatus, text: string) {
  const current = item.value;
  if (!current) return;
  return act(async () => {
    const opts = status === "harvested" ? { note: text } : status === "deferred" ? {} : { decision: text };
    const out = await closeItem(worldSlug.value, current.id, status, opts);
    prompt.value = null;
    queue.value = queue.value.filter((i) => i.id !== current.id);
    if (index.value >= queue.value.length) index.value = Math.max(0, queue.value.length - 1);
    toast.value = {
      label: `${STATUS_LABELS[status]}${opts.decision ? " · decision logged" : ""}`,
      undo: async () => {
        await undoClose(worldSlug.value, current.id, out.decision_id);
        // put it back where it was, as it was
        const at = Math.min(index.value, queue.value.length);
        queue.value.splice(at, 0, { ...out.item, status: "open", closed_at: null, closed_note: null, version: out.item.version + 1 });
        index.value = at;
      },
    };
    void session.refreshCounts(worldSlug.value);
  });
}

async function startEdit() {
  if (!item.value) return;
  draft.value = item.value.body;
  editing.value = true;
  await nextTick();
  editBox.value?.focus();
}

function saveEdit() {
  const current = item.value;
  if (!current) return;
  return act(async () => {
    replace(await updateItem(worldSlug.value, current, { body: draft.value }));
    editing.value = false;
  });
}

function setKind(kind: Item["kind"]) {
  const current = item.value;
  if (!current || current.kind === kind) return;
  return act(async () => replace(await updateItem(worldSlug.value, current, { kind })));
}

function setProject(slug: string) {
  const current = item.value;
  if (!current) return;
  return act(async () => replace(await updateItem(worldSlug.value, current, { project: slug || null })));
}

function step(by: number) {
  index.value = Math.min(Math.max(0, index.value + by), Math.max(0, queue.value.length - 1));
}

function onKey(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null;
  const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT");
  if (prompt.value) {
    if (e.key === "Escape") prompt.value = null;
    return;
  }
  if (tagging.value) {
    if (e.key === "Escape") tagging.value = false;
    return;
  }
  if (editing.value) {
    if (e.key === "Escape") editing.value = false;
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void saveEdit();
    return;
  }
  if (typing || e.ctrlKey || e.metaKey || e.altKey || busy.value) return;
  const keys: Record<string, () => unknown> = {
    a: () => ask("accepted"),
    r: () => ask("rejected"),
    h: () => ask("harvested"),
    d: () => ask("deferred"),
    e: startEdit,
    l: startTag,
    p: () => projectSelect.value?.focus(),
    j: () => step(1),
    k: () => step(-1),
    ArrowRight: () => step(1),
    ArrowLeft: () => step(-1),
    "1": () => setKind("spark"),
    "2": () => setKind("question"),
    "3": () => setKind("task"),
    u: undoLast,
    "?": () => (showKeys.value = !showKeys.value),
  };
  const fn = keys[e.key];
  if (fn) {
    e.preventDefault();
    void fn();
  }
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));

const VERBS: Record<CloseStatus, string> = { accepted: "accept", rejected: "reject", harvested: "harvest", deferred: "defer" };

async function undoLast() {
  const t = toast.value;
  if (!t) return;
  toast.value = null;
  await act(t.undo);
}

const promptLabel = computed(() =>
  prompt.value === "harvested" ? "What's worth keeping? (optional)" : "Decision (optional)",
);
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'inbox', params: { world: world.slug } }">Inbox</RouterLink>
        </div>
        <h1>Triage</h1>
      </div>
      <div class="actions">
        <ProjectFilter v-model="project" :world="world" />
        <span v-if="queue.length" class="muted small" data-testid="triage-position">
          {{ index + 1 }} of {{ queue.length }}
        </span>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <p v-if="loading" class="muted">Loading…</p>
    <section v-else-if="!item" class="card triage-done">
      <h2>Inbox clear</h2>
      <p class="muted">Nothing open {{ project ? "here" : "in this world" }}.</p>
      <RouterLink :to="{ name: 'decisions', params: { world: world.slug } }">See the decisions log</RouterLink>
    </section>
    <section v-else class="card triage-card" data-testid="triage-item">
      <div class="triage-meta">
        <span class="pill" :class="`kind-${item.kind}`">{{ item.kind }}</span>
        <span class="pill">{{ projectName(item.project) }}</span>
        <span class="muted small">{{ age(item.created_at) }}<template v-if="item.source"> · from {{ item.source }}</template></span>
      </div>

      <template v-if="editing">
        <label for="triage-edit" class="visually-hidden">Text</label>
        <textarea id="triage-edit" ref="editBox" v-model="draft" class="capture-box prose-box" rows="8" />
        <div class="actions">
          <button type="button" class="btn btn-sm btn-primary" @click="saveEdit">Save</button>
          <button type="button" class="btn btn-sm" @click="editing = false">Cancel</button>
          <span class="muted small">Ctrl+Enter saves, Esc cancels</span>
        </div>
      </template>
      <p v-else class="prose triage-text">
        <MentionText
          :text="item.body"
          :mentions="item.mentions"
          :world="world.slug"
          :source="{ table: 'item', id: item.id }"
          @fixed="reloadCurrent"
        />
      </p>

      <div class="chips triage-tags">
        <span v-for="t in item.entities" :key="t.id" class="chip static tag">
          <RouterLink :to="{ name: 'entity', params: { world: world.slug, id: t.id } }">{{ t.name }}</RouterLink>
          <button type="button" class="chip-x" :aria-label="`Untag ${t.name}`" @click="untag(t)">×</button>
        </span>
        <button v-if="!tagging" type="button" class="chip" @click="startTag"><kbd>l</kbd> Tag</button>
      </div>
      <EntityPicker
        v-if="tagging"
        ref="picker"
        :entities="names"
        :exclude="item.entities.map((t) => t.id)"
        @pick="tag"
        @cancel="tagging = false"
      />

      <form v-if="prompt" class="triage-prompt" @submit.prevent="finish(prompt, promptText)">
        <label for="triage-prompt">{{ promptLabel }}</label>
        <input id="triage-prompt" ref="promptBox" v-model="promptText" type="text" maxlength="1000" autocomplete="off" />
        <div class="actions">
          <button class="btn btn-sm btn-primary verb" type="submit" :disabled="busy">{{ VERBS[prompt] }}</button>
          <span class="muted small">Enter to {{ VERBS[prompt] }}, Esc to go back</span>
        </div>
      </form>

      <div v-else-if="!editing" class="triage-keys">
        <button type="button" class="btn btn-primary" :disabled="busy" @click="ask('accepted')"><kbd>a</kbd> Accept</button>
        <button type="button" class="btn" :disabled="busy" @click="ask('rejected')"><kbd>r</kbd> Reject</button>
        <button type="button" class="btn" :disabled="busy" @click="ask('harvested')"><kbd>h</kbd> Harvest</button>
        <button type="button" class="btn" :disabled="busy" @click="ask('deferred')"><kbd>d</kbd> Defer</button>
        <span class="spacer" />
        <button type="button" class="btn btn-sm" @click="startEdit"><kbd>e</kbd> Edit</button>
        <label for="triage-project" class="visually-hidden">Project</label>
        <select
          id="triage-project"
          ref="projectSelect"
          class="filter"
          :value="item.project ?? ''"
          @change="setProject(($event.target as HTMLSelectElement).value)"
        >
          <option value="">Whole world</option>
          <option v-for="p in world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
      </div>

      <p class="muted small triage-help">
        <button type="button" class="linkish small" @click="showKeys = !showKeys">Keys</button>
        <template v-if="showKeys">
          · <kbd>j</kbd>/<kbd>k</kbd> next and previous · <kbd>1</kbd> spark <kbd>2</kbd> question <kbd>3</kbd> task ·
          <kbd>p</kbd> project · <kbd>u</kbd> undo
        </template>
      </p>
    </section>

    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" @dismiss="toast = null" />
  </template>
</template>
