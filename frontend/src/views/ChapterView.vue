<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";

import { entityNames, fixes } from "../bible";
import HistoryPanel from "../components/HistoryPanel.vue";
import { createProse, countWords, type Prose } from "../editor/prose";
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
import { useSession } from "../stores/session";
import { localToday, type EntityRef } from "../types";
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

const focusMode = ref(false);
const typewriter = ref(false);
const showHistory = ref(false);
const names = ref<EntityRef[]>([]);
const project = computed(() => world.value?.projects.find((p) => p.slug === chapter.value?.project));
const readOnly = computed(() => chapter.value?.state === "retired");

const STATUS_TEXT: Record<SaveStatus, string> = {
  saved: "Saved",
  unsaved: "Not saved yet",
  saving: "Saving…",
  offline: "Offline: kept here, retrying",
  conflict: "Changed elsewhere: your text is in History",
};

// the names in this chapter, for the side panel
const inChapter = computed(() => {
  const counts = new Map<string, { id: string; name: string; count: number }>();
  for (const m of chapter.value?.mentions ?? []) {
    if (m.kind === "near_miss") continue;
    const c = counts.get(m.entity_id) ?? { id: m.entity_id, name: m.entity_name, count: 0 };
    c.count++;
    counts.set(m.entity_id, c);
  }
  return [...counts.values()].sort((a, b) => b.count - a.count);
});
const nearMissCount = computed(() => chapter.value?.mentions.filter((m) => m.kind === "near_miss").length ?? 0);

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
      words.value = countWords(text);
      saver?.edit({ body: text });
    },
    onSave: () => void checkpoint(),
    onNearMiss: (info) => (menu.value = info),
  });
  prose.value.setMentions(ch.mentions);
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
      // fresh name marks, if nothing was typed while the save was on its way
      if (sentBody !== undefined && sentBody === current) prose.value?.setMentions(saved.mentions);
    },
    conflict: (current) => {
      chapter.value = current;
      prose.value?.replaceDoc(current.body);
      prose.value?.setMentions(current.mentions);
      saver?.rebase(current);
      notice.value = "This chapter was changed on another device. Its text is shown now; yours was kept in History as a conflict copy.";
    },
    status: (s) => (status.value = s),
  });
}

async function load() {
  missing.value = false;
  try {
    const ch = await getChapter(worldSlug.value, String(route.params.id));
    chapter.value = ch;
    await nextTick();
    mount(ch);
  } catch {
    missing.value = true;
  }
}

onMounted(async () => {
  await load();
  names.value = await entityNames(worldSlug.value);
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

watch(focusMode, (on) => prose.value?.setFocusMode(on));
watch(typewriter, (on) => prose.value?.setTypewriter(on));
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

// ---- near-miss menu in the editor ----
const menu = ref<{ word: string; entityId: string; name: string; from: number; to: number; x: number; y: number } | null>(null);
async function fixNearMiss(kind: "replace" | "spelling" | "ignore") {
  const m = menu.value;
  if (!m || !chapter.value) return;
  menu.value = null;
  if (kind === "replace") {
    prose.value?.replaceRange(m.from, m.to, m.name);
    return;
  }
  await saver?.flush();
  if (kind === "spelling") await fixes.addSpelling(worldSlug.value, m.word, m.entityId);
  else await fixes.notATypo(worldSlug.value, m.word);
  const fresh = await getChapter(worldSlug.value, chapter.value.id);
  if (fresh.body === prose.value?.view.state.doc.toString()) prose.value?.setMentions(fresh.mentions);
  chapter.value = { ...fresh };
  void session.refreshNearMisses(worldSlug.value);
}

// ---- side panel actions ----
async function setPov(id: string) {
  if (!chapter.value) return;
  await saver?.flush();
  try {
    const ch = await saveChapter(worldSlug.value, chapter.value.id, chapter.value.version, { pov_entity_id: id || null });
    chapter.value = { ...ch, body: prose.value?.view.state.doc.toString() ?? ch.body };
    saver?.rebase(ch);
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function restore(revisionId: string) {
  if (!chapter.value) return;
  await saver?.flush();
  const ch = await restoreRevision(worldSlug.value, chapter.value.id, revisionId);
  chapter.value = ch;
  showHistory.value = false;
  prose.value?.replaceDoc(ch.body);
  prose.value?.setMentions(ch.mentions);
  title.value = ch.title;
  saver?.rebase(ch);
  notice.value = "Restored. The text it replaced is in History.";
}

const experimentFrom = ref<"copy" | "scratch">("copy");
async function experiment() {
  if (!chapter.value) return;
  await saver?.leave();
  const ch = await startExperiment(worldSlug.value, chapter.value.id, experimentFrom.value);
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
      <div ref="host" class="editor-host" :class="{ focus: focusMode }" data-testid="editor" />

      <div v-if="menu" class="fix-menu floating" role="menu" :style="{ left: `${menu.x}px`, top: `${menu.y + 6}px` }">
        <span class="fix-title">Did you mean <strong>{{ menu.name }}</strong>?</span>
        <button type="button" role="menuitem" @click="fixNearMiss('replace')">Replace with {{ menu.name }}</button>
        <button type="button" role="menuitem" @click="fixNearMiss('spelling')">“{{ menu.word }}” is another spelling</button>
        <button type="button" role="menuitem" @click="fixNearMiss('ignore')">Not a typo</button>
        <button type="button" role="menuitem" class="muted" @click="menu = null">Close</button>
      </div>
    </div>

    <aside v-if="chapter && !showHistory" class="chapter-side">
      <section>
        <h3 class="small muted">Point of view</h3>
        <select class="filter" aria-label="Point of view" :value="chapter.pov?.id ?? ''" :disabled="readOnly" @change="setPov(($event.target as HTMLSelectElement).value)">
          <option value="">None</option>
          <option v-for="e in names.filter((n) => n.kind === 'character')" :key="e.id" :value="e.id">{{ e.name }}</option>
        </select>
      </section>
      <section>
        <h3 class="small muted">In this chapter</h3>
        <ul class="plain-list">
          <li v-for="e in inChapter" :key="e.id">
            <RouterLink :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
            <span class="muted small">×{{ e.count }}</span>
          </li>
          <li v-if="!inChapter.length" class="muted small">No names from the bible yet.</li>
        </ul>
        <p v-if="nearMissCount" class="small">
          <RouterLink :to="{ name: 'names', params: { world: world.slug } }">{{ nearMissCount }} possible misspelling(s)</RouterLink>
        </p>
      </section>
      <section v-if="chapter.harvest_notes.length">
        <h3 class="small muted">Harvest notes</h3>
        <p v-for="n in chapter.harvest_notes" :key="n.id" class="small">{{ n.body }}</p>
      </section>
      <section class="side-actions">
        <button type="button" class="btn btn-sm" :disabled="readOnly" @click="checkpoint">Checkpoint <kbd>Ctrl S</kbd></button>
        <template v-if="chapter.state === 'current'">
          <div class="actions">
            <select v-model="experimentFrom" class="filter" aria-label="Experiment starts from">
              <option value="copy">from a copy</option>
              <option value="scratch">from scratch</option>
            </select>
            <button type="button" class="btn btn-sm" @click="experiment">Start an experiment</button>
          </div>
          <button type="button" class="btn btn-sm" @click="closing = 'retire'">Retire to Salvage</button>
        </template>
      </section>
    </aside>

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
