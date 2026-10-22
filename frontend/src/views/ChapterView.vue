<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";

import { addRelationship, createEntity, fixes, getEntity, typeOptions, updateEntity } from "../bible";
import ChapterSide from "../components/ChapterSide.vue";
import HistoryPanel from "../components/HistoryPanel.vue";
import { createProse, countWords, type Prose, type WorldHooks } from "../editor/prose";
import { ChapterSaver, type SaveStatus } from "../editor/saver";
import {
  closeExperiment,
  getChapter,
  reinstateChapter,
  restoreRevision,
  retireChapter,
  saveChapter,
  snapshot,
  startExperiment,
  type Chapter,
} from "../manuscript";
import { ApiError } from "../api";
import { cacheChapter, dropDraft, getDraft, localChapter, queueRevision, saveDraft } from "../offline";
import { usePrefs } from "../prefs";
import { useSession } from "../stores/session";
import { localToday } from "../types";
import { useCards } from "../world/cards";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const chapter = ref<Chapter | null>(null);
const missing = ref(false);
const title = ref("");
const words = ref(0);
const status = ref<SaveStatus>("saved");
const notice = ref("");
const error = ref("");
const host = ref<HTMLElement | null>(null);
const prose = shallowRef<Prose | null>(null);
let saver: ChapterSaver | null = null;

const prefs = usePrefs();
const cards = useCards();
const focusMode = ref(prefs.focusMode);
const typewriter = ref(prefs.typewriter);
const showHistory = ref(false);
const project = computed(() => world.value?.projects.find((p) => p.slug === chapter.value?.project));
// shown from the copy on this device: the server couldn't be reached
const offlineCopy = ref(false);
let draftTimer: ReturnType<typeof setTimeout> | undefined;

/** Keep what's in the editor on this device until the server has it. */
// the word count over a whole chapter is too slow for every keystroke on a phone: it catches up when typing pauses
let countTimer = 0;
function countLater(text: string) {
  clearTimeout(countTimer);
  countTimer = window.setTimeout(() => (words.value = countWords(text)), 300);
}

function keepDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    const ch = chapter.value;
    const body = prose.value?.view.state.doc.toString();
    if (!ch || body === undefined || !saver) return;
    void saveDraft({ chapterId: ch.id, world: worldSlug.value, title: title.value, body, baseVersion: saver.currentVersion });
  }, 400);
}
const readOnly = computed(() => chapter.value?.state === "retired");

const STATUS_TEXT: Record<SaveStatus, string> = {
  saved: "Saved",
  unsaved: "Not saved yet",
  saving: "Saving…",
  offline: "Offline: kept here, retrying",
  conflict: "Changed elsewhere: your text is in History",
};


function mount(ch: Chapter) {
  prose.value?.destroy();
  saver?.close();
  title.value = ch.title;
  words.value = countWords(ch.body);
  if (!host.value) return;
  prose.value = createProse(host.value, {
    doc: ch.body,
    readOnly: ch.state === "retired",
    placeholderText: ch.state === "experiment" && !ch.body ? "Start the rewrite from a blank page…" : "Write…",
    onChange: (text) => {
      countLater(text);
      saver?.edit({ body: text });
      keepDraft();
    },
    onSave: () => void checkpoint(),
    world: worldHooks,
  });
  prose.value.setFocusMode(focusMode.value);
  prose.value.setTypewriter(typewriter.value);
  saver = new ChapterSaver(ch, {
    save: (v, changes) => saveChapter(worldSlug.value, ch.id, v, changes),
    snapshot: (reason, extra) => snapshot(worldSlug.value, ch.id, reason, extra),
    now: () => Date.now(),
  }, {
    saved: (saved, sentBody) => {
      const current = prose.value?.view.state.doc.toString();
      chapter.value = { ...saved, body: current ?? saved.body };
      offlineCopy.value = false;
      void cacheChapter(worldSlug.value, saved);
      void dropDraft(saved.id, sentBody);
      void sentBody;
    },
    conflict: (current) => {
      chapter.value = current;
      void dropDraft(current.id);
      void cacheChapter(worldSlug.value, current);
      prose.value?.replaceDoc(current.body);
      saver?.rebase(current);
      notice.value = "This chapter was changed on another device. Its text is shown now; yours was kept in History as a conflict copy.";
    },
    status: (s) => (status.value = s),
  });
}

async function load() {
  missing.value = false;
  offlineCopy.value = false;
  const id = String(route.params.id);
  let ch: Chapter | undefined;
  try {
    ch = await getChapter(worldSlug.value, id);
    void cacheChapter(worldSlug.value, ch);
  } catch (e) {
    if (e instanceof ApiError && e.status === 0) {
      ch = await localChapter(id);
      offlineCopy.value = !!ch;
    }
  }
  if (!ch) {
    missing.value = true;
    return;
  }
  chapter.value = ch;
  await nextTick();
  mount(ch);
  await recoverDraft(ch);
}

/** Text written on this device that never reached the server (a reload, a closed app, no signal). */
async function recoverDraft(ch: Chapter) {
  const draft = await getDraft(ch.id);
  if (!draft || (draft.body === ch.body && draft.title === ch.title)) {
    if (draft) void dropDraft(ch.id);
    return;
  }
  if (draft.baseVersion === ch.version) {
    // nothing changed elsewhere: carry on where this device left off
    prose.value?.replaceDoc(draft.body);
    if (draft.title && draft.title !== ch.title) title.value = draft.title;
    notice.value = "Text from this device that wasn't saved yet is back in the editor.";
    return;
  }
  // the chapter moved on elsewhere: keep this device's text in History instead of overwriting either
  const label = "Written on this device while another version was saved";
  try {
    await snapshot(worldSlug.value, ch.id, "conflict", { body: draft.body, label });
  } catch {
    await queueRevision({ world: worldSlug.value, chapterId: ch.id, reason: "conflict", label, body: draft.body });
  }
  await dropDraft(ch.id);
  notice.value = "This chapter changed elsewhere since this device last wrote in it. That text is kept in History as a conflict copy.";
}

onMounted(async () => {
  void cards.load(worldSlug.value);
  await load();
  document.addEventListener("visibilitychange", onHide);
  window.addEventListener("beforeunload", onUnload);
});
watch(() => route.params.id, async (id, old) => {
  if (id && id !== old) {
    await saver?.leave();
    await load();
  }
});
onBeforeRouteLeave(async () => {
  await saver?.leave();
});
onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", onHide);
  window.removeEventListener("beforeunload", onUnload);
  saver?.close();
  prose.value?.destroy();
});

function onHide() {
  if (document.visibilityState === "hidden") void saver?.leave();
}
function onUnload(e: BeforeUnloadEvent) {
  if (saver?.dirty) {
    void saver.flush();
    e.preventDefault();
  }
}

watch(focusMode, (on) => {
  prose.value?.setFocusMode(on);
  prefs.set("focusMode", on);
});
watch(typewriter, (on) => {
  prose.value?.setTypewriter(on);
  prefs.set("typewriter", on);
});

// ---- the world in the editor: names coloured by kind, cards and quick fixes (docs/WORLD-MODEL.md §5) ----
let matcher = cards.matcher();
watch(
  () => cards.version,
  () => {
    matcher = cards.matcher();
    prose.value?.refreshNames();
  },
);
watch(() => ({ ...prefs.$state }), () => prose.value?.refreshPrefs(), { deep: true });
const names = computed(() => cards.names);

async function worldChange(fn: () => Promise<unknown>) {
  error.value = "";
  try {
    await fn();
    await cards.refresh(worldSlug.value);
    void session.refreshNearMisses(worldSlug.value);
  } catch (e) {
    error.value = (e as Error).message;
  }
}

const worldHooks: WorldHooks = {
  matcher: () => matcher,
  card: (id) => cards.byId.get(id),
  names: () => cards.names,
  prefs: () => prefs.$state,
  open: (id) => void router.push({ name: "entity", params: { world: worldSlug.value, id } }),
  addName: (id, word) => worldChange(() => fixes.addSpelling(worldSlug.value, word, id)),
  notATypo: (word) => worldChange(() => fixes.notATypo(worldSlug.value, word)),
  create: (name, kind) => worldChange(() => createEntity(worldSlug.value, { name, kind })),
  exclude: (id, phrase) =>
    worldChange(async () => {
      const { entity } = await getEntity(worldSlug.value, id);
      await updateEntity(worldSlug.value, entity, { exclusions: [...entity.exclusions, phrase] });
    }),
  link: (id) => ({
    names: () => cards.names,
    options: (other) => {
      const from = cards.byId.get(id)?.kind ?? "other";
      return typeOptions(cards.types, from, other.kind).map((o) => ({ key: `${o.type.id}|${o.forward}`, reads: o.reads }));
    },
    add: (other, key) => {
      const [typeId, forward] = key.split("|");
      const [a, b] = forward === "true" ? [id, other.id] : [other.id, id];
      return worldChange(() => addRelationship(worldSlug.value, { type_id: typeId!, a_id: a, b_id: b, established_in_chapter_id: chapter.value?.id ?? null }));
    },
  }),
};
const editorStyle = computed(() => ({ "--prose-size": `${prefs.textSize}px`, "--prose-width": `${prefs.lineWidth}ch` }));
watch(title, (t) => {
  if (chapter.value && t.trim() && t !== chapter.value.title) saver?.edit({ title: t });
});

// ---- checkpoint (Ctrl+S) with an optional label ----
const labelling = ref(false);
const label = ref("");
const labelBox = ref<HTMLInputElement | null>(null);

async function checkpoint() {
  labelling.value = true;
  label.value = "";
  await nextTick();
  labelBox.value?.focus();
}
async function keepCheckpoint() {
  labelling.value = false;
  await saver?.checkpoint(label.value.trim() || undefined);
  notice.value = label.value.trim() ? `Checkpoint “${label.value.trim()}” kept.` : "Checkpoint kept.";
  prose.value?.view.focus();
}

// ---- side panel actions ----
async function setPov(id: string) {
  // through the save queue, so it can't race the autosave of the text
  saver?.edit({ pov_entity_id: id || null });
  await saver?.flush();
}

async function restore(revisionId: string, body: string) {
  if (!chapter.value) return;
  await saver?.flush();
  let ch: Chapter;
  try {
    ch = await restoreRevision(worldSlug.value, chapter.value.id, revisionId);
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 0) throw e;
    // offline: put the old text in the editor (it saves when the connection is back), and keep the text it
    // replaces on this device until it can be sent as a snapshot
    const current = prose.value?.view.state.doc.toString() ?? "";
    await queueRevision({ world: worldSlug.value, chapterId: chapter.value.id, reason: "restore",
                          label: "Before restoring an older version (offline)", body: current });
    showHistory.value = false;
    prose.value?.replaceDoc(body);
    notice.value = "Restored on this device. It's saved when you're back online; the text it replaced is kept.";
    return;
  }
  chapter.value = ch;
  showHistory.value = false;
  prose.value?.replaceDoc(ch.body);
  title.value = ch.title;
  saver?.rebase(ch);
  notice.value = "Restored. The text it replaced is in History.";
}

async function experiment(from: "copy" | "scratch") {
  if (!chapter.value) return;
  await saver?.leave();
  const ch = await startExperiment(worldSlug.value, chapter.value.id, from);
  await router.push({ name: "chapter", params: { world: worldSlug.value, id: ch.id } });
}

const closing = ref<"accepted" | "harvested" | "rejected" | "retire" | null>(null);
const note = ref("");
const decision = ref("");
async function confirmClose() {
  const ch = chapter.value;
  if (!ch || !closing.value) return;
  await saver?.leave();
  error.value = "";
  try {
    if (closing.value === "retire") {
      await retireChapter(worldSlug.value, ch.id, note.value);
    } else {
      await closeExperiment(worldSlug.value, ch.id, closing.value, {
        note: note.value || undefined,
        decision: decision.value || undefined,
        decided_on: localToday(),
      });
    }
    const outcome = closing.value;
    closing.value = null;
    note.value = decision.value = "";
    if (outcome === "accepted") {
      await load();
      notice.value = "Accepted: this draft is now the chapter. The old one is in Salvage.";
    } else {
      await router.push({ name: "project", params: { world: worldSlug.value, project: ch.project } });
    }
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function reinstate() {
  if (!chapter.value) return;
  await reinstateChapter(worldSlug.value, chapter.value.id);
  await load();
  notice.value = "Back in the book, as the last chapter.";
}

const CLOSE_TEXT = {
  accepted: { verb: "Accept", note: "Anything worth keeping from the old chapter? (optional)" },
  harvested: { verb: "Harvest", note: "What was alive in this draft?" },
  rejected: { verb: "Reject", note: "Why, or what to remember? (optional)" },
  retire: { verb: "Retire", note: "What was alive in this chapter? (optional)" },
} as const;
</script>

<template>
  <NotFoundView v-if="!world || missing" what="chapter" />
  <div v-else class="chapter-page" :class="{ 'with-history': showHistory }">
    <div class="chapter-main">
      <div class="chapter-bar">
        <div class="crumbs">
          <RouterLink v-if="project" :to="{ name: 'project', params: { world: world.slug, project: project.slug } }">{{ project.name }}</RouterLink>
          <template v-if="chapter?.state === 'experiment'"> · Experiment</template>
          <template v-if="chapter?.state === 'retired'"> · Salvage</template>
        </div>
        <div class="chapter-tools">
          <span class="muted small" data-testid="save-status" :class="`status-${status}`">{{ STATUS_TEXT[status] }}</span>
          <span class="muted small" data-testid="word-count">{{ words.toLocaleString() }} words</span>
          <label class="toggle"><input v-model="focusMode" type="checkbox" /> Focus</label>
          <label class="toggle desk-only"><input v-model="typewriter" type="checkbox" /> Typewriter</label>
          <button type="button" class="btn btn-sm" @click="showHistory = !showHistory">History</button>
        </div>
      </div>

      <div v-if="chapter?.state === 'experiment'" class="notice accent experiment-bar" data-testid="experiment-bar">
        <span>
          Rewrite of <strong>{{ chapter.replaces_title ?? "a chapter" }}</strong>.
          <template v-if="chapter.replaces_id">
            <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: chapter.replaces_id } }">Peek at the old one</RouterLink>
          </template>
        </span>
        <span class="actions">
          <button type="button" class="btn btn-sm btn-primary" @click="closing = 'accepted'">Accept</button>
          <button type="button" class="btn btn-sm" @click="closing = 'harvested'">Harvest</button>
          <button type="button" class="btn btn-sm" @click="closing = 'rejected'">Reject</button>
        </span>
      </div>
      <div v-if="chapter?.state === 'retired'" class="notice experiment-bar">
        <span>Retired: kept in Salvage, read-only.</span>
        <button type="button" class="btn btn-sm" @click="reinstate">Put back in the book</button>
      </div>

      <form v-if="closing" class="card form wide close-form" @submit.prevent="confirmClose">
        <div class="field">
          <label for="close-note">{{ CLOSE_TEXT[closing].note }}</label>
          <textarea id="close-note" v-model="note" class="capture-box" rows="3" :required="closing === 'harvested'" />
        </div>
        <div v-if="closing === 'accepted' || closing === 'rejected'" class="field">
          <label for="close-decision">Decision (optional)</label>
          <input id="close-decision" v-model="decision" type="text" maxlength="1000" />
        </div>
        <div class="actions">
          <button class="btn btn-primary" type="submit">{{ CLOSE_TEXT[closing].verb }}</button>
          <button class="btn" type="button" @click="closing = null">Cancel</button>
        </div>
      </form>

      <div v-if="offlineCopy" class="notice offline small" role="status" data-testid="offline-copy">
        Offline: this is the copy on this device. What you write is kept here and saved when you're back.
      </div>
      <div v-if="notice" class="notice ok small" role="status" @click="notice = ''">{{ notice }}</div>
      <div v-if="error" class="notice error small" role="alert">{{ error }}</div>

      <form v-if="labelling" class="checkpoint-bar" @submit.prevent="keepCheckpoint">
        <label for="checkpoint-label">Checkpoint label (optional)</label>
        <input id="checkpoint-label" ref="labelBox" v-model="label" type="text" maxlength="200" @keydown.esc="labelling = false" />
        <button class="btn btn-sm btn-primary" type="submit">Keep</button>
      </form>

      <div class="title-wrap">
        <input v-model="title" class="chapter-title" aria-label="Chapter title" maxlength="300" :readonly="readOnly" />
      </div>
      <div ref="host" class="editor-host" :class="{ focus: focusMode }" :style="editorStyle" data-testid="editor" />
    </div>

    <ChapterSide
      v-if="chapter && !showHistory"
      :world="world.slug"
      :chapter="chapter"
      :names="names"
      :read-only="readOnly"
      @pov="setPov"
      @checkpoint="checkpoint"
      @experiment="experiment"
      @retire="closing = 'retire'"
    />

    <HistoryPanel
      v-if="showHistory && chapter"
      :world="world.slug"
      :chapter-id="chapter.id"
      :current="prose?.view.state.doc.toString() ?? chapter.body"
      @restore="restore"
      @close="showHistory = false"
    />
  </div>
</template>
