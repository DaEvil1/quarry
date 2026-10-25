<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter, type RouteLocationRaw } from "vue-router";

import { addRelationship, createEntity, endBefore as endBeforeRole, fixes, getEntity, setLabelSwitches, typeOptions, updateEntity } from "../bible";
import ChapterSide from "../components/ChapterSide.vue";
import CompanionPanel from "../components/CompanionPanel.vue";
import {
  chapterItems,
  checks as loadChecksApi,
  linkedPairs,
  resolutions,
  resolve as resolveApi,
  saveSessionNote,
  sessionNote,
  type Check,
  type PanelActions,
} from "../companion";
import type { Since } from "../editor/companion";
import { chapterPresence, setPresence } from "../storytime";
import HistoryPanel from "../components/HistoryPanel.vue";
import UndoToast from "../components/UndoToast.vue";
import { EditorView } from "@codemirror/view";

import { around, chapterCuts, cutLabel, findPlace, listCuts, markPutBack, removeCut, type Cut } from "../cuts";
import { changesLine, changesSince } from "../editor/changes";
import { createProse, countWords, type Prose, type WorldHooks } from "../editor/prose";
import { ChapterSaver, type SaveStatus } from "../editor/saver";
import {
  closeExperiment,
  getChapter,
  reinstateChapter,
  restoreRevision,
  retireChapter,
  saveChapter,
  setAbout,
  snapshot,
  startExperiment,
  statuses as statusApi,
  type Chapter,
  type StatusRef,
} from "../manuscript";
import { unreachable } from "../api";
import {
  cacheChapter,
  checkpointBody,
  dropDraft,
  getDraft,
  labelledCheckpoints,
  localChapter,
  queueRevision,
  saveDraft,
  type Checkpoint,
} from "../offline";
import { usePrefs } from "../prefs";
import { useOutbox } from "../stores/outbox";
import { useSession } from "../stores/session";
import { localToday, type EntityRef, type Presence } from "../types";
import { useCards } from "../world/cards";
import { analyse, linkKey, storyText, type Finding } from "../world/findings";
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
  countTimer = window.setTimeout(() => (words.value = countWords(storyText(text))), 300);
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
  words.value = countWords(storyText(ch.body));
  wordsAtOpen = words.value;
  asked = false;
  if (!host.value) return;
  prose.value = createProse(host.value, {
    doc: ch.body,
    readOnly: ch.state === "retired",
    placeholderText: ch.state === "experiment" && !ch.body ? "Start the rewrite from a blank page…" : "Write…",
    onChange: (text) => {
      countLater(text);
      saver?.edit({ body: text });
      keepDraft();
      scheduleAnalysis();
      scheduleChanges();
    },
    onSave: () => void checkpoint(),
    onFindAll: (text) =>
      void router.push({ name: "replace", params: { world: worldSlug.value, project: ch.project }, query: text ? { find: text } : {} }),
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
      if (panelTab.value === "continuity") void loadChecks();
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
    if (unreachable(e)) {
      ch = await localChapter(id);
      offlineCopy.value = !!ch;
    }
  }
  if (!ch) {
    missing.value = true;
    return;
  }
  chapter.value = ch;
  toast.value = null;
  void loadPresence(ch.id);
  await nextTick();
  mount(ch);
  await recoverDraft(ch);
  void loadCompanion(ch);
  void loadStatuses(ch);
  void loadCuts(ch);
  void loadSince(ch);
  await openAt();
}

/** Opened at a place (from reading an entry's thread, or a find in all chapters), or to put a cut back (Salvage). */
async function openAt() {
  const p = prose.value;
  const ch = chapter.value;
  if (!p || !ch) return;
  const at = typeof route.query.at === "string" ? Number(route.query.at) : NaN;
  if (Number.isFinite(at)) {
    const pos = Math.max(0, Math.min(at, p.view.state.doc.length));
    p.view.dispatch({ selection: { anchor: pos }, effects: EditorView.scrollIntoView(pos, { y: "center" }) });
    p.view.focus();
  }
  const cutId = typeof route.query.putback === "string" ? route.query.putback : null;
  if (cutId && !readOnly.value) {
    const from = typeof route.query.from === "string" ? route.query.from : ch.project;
    void router.replace({ query: { ...route.query, putback: undefined, from: undefined } });
    try {
      const cut = (await listCuts(worldSlug.value, from, "", true)).find((c) => c.id === cutId);
      if (cut) await putBack(cut, "place", true);
    } catch (e) {
      error.value = (e as Error).message;
    }
  }
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
    keepPlace();
    await saver?.leave();
    await load();
  }
});
onBeforeRouteLeave(async (to) => {
  // wrote something this time: ask (once, skippably) for a note for next time
  if (!asked && prefs.askNote && !readOnly.value && chapter.value && words.value - wordsAtOpen >= 30) {
    asked = true;
    leaving.value = to.fullPath;
    leaveNote.value = nextNote.value;
    await nextTick();
    leaveBox.value?.focus();
    return false;
  }
  keepPlace();
  await saver?.leave();
});
onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", onHide);
  window.removeEventListener("beforeunload", onUnload);
  saver?.close();
  prose.value?.destroy();
});

function onHide() {
  if (document.visibilityState === "hidden") {
    keepPlace();
    void saver?.leave();
  }
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
let matcherVersion = cards.version;
/** The matcher for the world's names as they are now (rebuilt when the cards change). */
function currentMatcher() {
  if (matcherVersion !== cards.version) {
    matcher = cards.matcher();
    matcherVersion = cards.version;
  }
  return matcher;
}
watch(
  () => cards.version,
  () => {
    currentMatcher();
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

// where characters are in this chapter ("is at"), for their cards
const presence = ref<Presence[]>([]);
async function loadPresence(chapterId: string) {
  try {
    presence.value = await chapterPresence(worldSlug.value, chapterId);
  } catch {
    presence.value = [];
  }
}
/** Pickers in a chapter list this book's entries and the world's first, other books' after them, labelled with their
 * book (docs/SPEC.md §12.4). */
function byLevel(list: EntityRef[]): (EntityRef & { where?: string })[] {
  const own = chapter.value?.project;
  const level = (id: string) => cards.byId.get(id)?.project ?? null;
  const mine = list.filter((n) => !level(n.id) || level(n.id) === own);
  const others = list.filter((n) => level(n.id) && level(n.id) !== own);
  const bookName = (slug: string) => world.value?.projects.find((p) => p.slug === slug)?.name ?? slug;
  return [...mine, ...others.map((n) => ({ ...n, where: bookName(level(n.id)!) }))];
}
/** places for "is at…": the ones named in this chapter first, then the rest */
function placesForChapter(): EntityRef[] {
  const named = new Set((chapter.value?.mentions ?? []).filter((m) => m.entity_kind === "place").map((m) => m.entity_id));
  const places = byLevel(cards.names.filter((n) => n.kind === "place"));
  return [...places.filter((p) => named.has(p.id)), ...places.filter((p) => !named.has(p.id))];
}

const worldHooks: WorldHooks = {
  matcher: currentMatcher,
  // the card as it reads at this chapter
  card: (id) => cards.asOf(cards.byId.get(id), chapter.value?.id ?? null),
  names: () => byLevel(cards.names),
  prefs: () => prefs.$state,
  open: (id) => void router.push({ name: "entity", params: { world: worldSlug.value, id } }),
  addName: (id, word) => worldChange(() => fixes.addSpelling(worldSlug.value, word, id)),
  notATypo: (word) => worldChange(() => fixes.notATypo(worldSlug.value, word)),
  // a new name made while writing starts in this chapter's book (docs/SPEC.md §12.4)
  create: (name, kind) => worldChange(() => createEntity(worldSlug.value, { name, kind, project: chapter.value?.project ?? null })),
  exclude: (id, phrase) =>
    worldChange(async () => {
      const { entity } = await getEntity(worldSlug.value, id);
      await updateEntity(worldSlug.value, entity, { exclusions: [...entity.exclusions, phrase] });
    }),
  get companion() {
    return companionHooks;
  },
  cut: (from, to) => void cutToBin(from, to),
  several: (kind, label) => cards.several(kind, label),
  isAt: (id) => ({
    here: () => presence.value.find((p) => p.entity_id === id)?.place ?? null,
    places: placesForChapter,
    set: async (place) => {
      const ch = chapter.value;
      if (!ch) return;
      try {
        await setPresence(worldSlug.value, ch.id, id, place.id);
        await loadPresence(ch.id);
      } catch (e) {
        error.value = (e as Error).message;
      }
    },
  }),
  link: (id) => ({
    names: () => byLevel(cards.names),
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
// ---- the writing companion (docs/WORLD-MODEL.md §7) ----
const mode = ref(prefs.mode);
watch(mode, (m) => {
  prefs.set("mode", m);
  analyseNow();
  showChanges();
});
const showPanel = ref(prefs.panel);
watch(showPanel, (on) => {
  prefs.set("panel", on);
  if (on && mode.value === "drafting") analyseNow();
});
const findings = shallowRef<Finding[]>([]);
let analysed: { since: Since; findings: Finding[] } | null = null;
const stale = ref(false);
const linked = ref(new Set<string>());
const resolved = ref(new Set<string>());
const chapterChecks = ref<Check[]>([]);
const items = ref<{ id: string; title: string | null; body: string }[]>([]);
const nextNote = ref("");
const backIn = ref<{ context: string; note: string; cursor: number } | null>(null);
let analyseTimer = 0;

/** Work out the findings for the text as it is now (live while Revising; at breaks while Drafting). */
function analyseNow() {
  clearTimeout(analyseTimer);
  const p = prose.value;
  const ch = chapter.value;
  if (!p || !ch || readOnly.value) return;
  const text = p.view.state.doc.toString();
  const since = p.since();
  const started = performance.now();
  const fs = analyse({
    text,
    matcher: currentMatcher(),
    card: (id) => cards.byId.get(id),
    linked: linked.value,
    presence: presence.value,
    resolved: resolved.value,
    longSentence: prefs.longSentence,
    project: ch.project,
    projectName: (slug) => world.value?.projects.find((p) => p.slug === slug)?.name ?? slug,
    expected: (kind) => cards.expected(kind),
  }).filter((f) => prefs.editors[f.editor].on);
  // visible in the browser's performance tools, and to the performance check (frontend/perf)
  performance.measure("quarry:analyse", { start: started });
  analysed = { since, findings: fs };
  findings.value = fs;
  stale.value = false;
  p.setMarks();
}
function scheduleAnalysis() {
  stale.value = true;
  if (mode.value !== "revising") return;
  clearTimeout(analyseTimer);
  analyseTimer = window.setTimeout(analyseNow, 700);
}
/** A finding's place in the text as it is now (or null if that bit of text was changed since). */
function placeOf(f: { from?: number; to?: number }): { from: number; to: number } | null {
  if (!analysed || f.from === undefined || f.to === undefined) return null;
  const from = analysed.since.map(f.from, 1);
  const to = analysed.since.map(f.to, -1);
  return to - from === f.to - f.from ? { from, to } : null;
}
function applyFix(f: Finding, at: { from: number } | null = placeOf(f)) {
  const p = prose.value;
  if (!p || !f.fix || f.from === undefined || !at) {
    notice.value = "That bit of text has changed since; the companion will look again.";
    analyseNow();
    return;
  }
  const d = at.from - f.from;
  p.view.dispatch({ changes: { from: f.fix.from + d, to: f.fix.to + d, insert: f.fix.insert } });
  analyseNow();
}

async function loadCompanion(ch: Chapter) {
  const w = worldSlug.value;
  const [pairs, res, chk, its, note] = await Promise.allSettled([
    linkedPairs(w),
    resolutions(w),
    loadChecksApi(w, ch.id),
    chapterItems(w, ch.id),
    sessionNote(w, ch.id),
  ]);
  if (chapter.value?.id !== ch.id) return;
  if (pairs.status === "fulfilled") linked.value = pairs.value;
  if (res.status === "fulfilled") resolved.value = new Set(res.value.map((r) => `${r.rule}|${r.key}`));
  if (chk.status === "fulfilled") chapterChecks.value = chk.value;
  if (its.status === "fulfilled") items.value = its.value;
  if (note.status === "fulfilled") {
    nextNote.value = note.value.note;
    const body = prose.value?.view.state.doc.toString() ?? ch.body;
    if (note.value.note || (note.value.cursor > 0 && note.value.cursor <= body.length)) {
      const at = Math.min(note.value.cursor, body.length);
      const start = body.lastIndexOf("\n", at - 1) + 1;
      const context = body.slice(Math.max(start, at - 60), at).trim();
      backIn.value = context || note.value.note ? { context, note: note.value.note, cursor: at } : null;
    }
  }
  analyseNow();
}
const loadChecks = async () => {
  if (chapter.value) chapterChecks.value = await loadChecksApi(worldSlug.value, chapter.value.id).catch(() => chapterChecks.value);
};

/** Where the writer is, and their note, kept for next time (best effort: offline it waits for the next visit). */
function keepPlace() {
  const ch = chapter.value;
  const p = prose.value;
  if (!ch || !p || readOnly.value) return;
  void saveSessionNote(worldSlug.value, ch.id, nextNote.value, p.view.state.selection.main.head).catch(() => {});
}

// leaving a chapter you wrote in: a note for next time, skippably
let wordsAtOpen = 0;
let asked = false;
const leaving = ref<RouteLocationRaw | null>(null);
const leaveNote = ref("");
const leaveBox = ref<HTMLInputElement | null>(null);
async function finishLeave(save: boolean) {
  if (save) nextNote.value = leaveNote.value.trim();
  const target = leaving.value;
  leaving.value = null;
  if (target) await router.push(target);
}

// stash a thought: to the inbox, tied to this chapter, without leaving the sentence
const outbox = useOutbox();
const stashing = ref(false);
const thought = ref("");
const stashBox = ref<HTMLInputElement | null>(null);
async function openStash() {
  stashing.value = true;
  thought.value = "";
  await nextTick();
  stashBox.value?.focus();
}
async function keepThought() {
  const text = thought.value.trim();
  const ch = chapter.value;
  stashing.value = false;
  prose.value?.view.focus();
  if (!text || !ch) return;
  const sent = await outbox.add({ world: worldSlug.value, body: text, kind: "spark", project: ch.project, source: "stash", chapterId: ch.id });
  notice.value = sent ? "Stashed in the inbox." : "Stashed on this device; it goes to the inbox when you're back online.";
  if (sent) items.value = await chapterItems(worldSlug.value, ch.id).catch(() => items.value);
}

// the panel's open tab: Continuity reloads its checks when opened, and after each save while it is open
const panelTab = ref("chapter");
function onTab(t: string) {
  panelTab.value = t;
  if (mode.value === "drafting") analyseNow();
  if (t === "continuity") void loadChecks();
}

async function afterWorldChange() {
  await loadChecks();
  analyseNow();
}

const panelActions: PanelActions = {
  jump(f) {
    const at = placeOf(f);
    const p = prose.value;
    if (!p || !at) return;
    p.view.dispatch({ selection: { anchor: at.from, head: at.to }, effects: EditorView.scrollIntoView(at.from, { y: "center" }) });
    p.view.focus();
  },
  fix: (f) => applyFix(f),
  async resolve(rule, key, outcome) {
    try {
      await resolveApi(worldSlug.value, rule, key, outcome);
      resolved.value = new Set([...resolved.value, `${rule}|${key}`]);
      await afterWorldChange();
    } catch (e) {
      error.value = (e as Error).message;
    }
  },
  async link(a, b, typeId, forward) {
    const [x, y] = forward ? [a, b] : [b, a];
    await worldChange(() => addRelationship(worldSlug.value, { type_id: typeId, a_id: x.id, b_id: y.id, established_in_chapter_id: chapter.value?.id ?? null }));
    linked.value = new Set([...linked.value, linkKey(a.id, b.id)]);
    analyseNow();
  },
  async isAt(entity, place) {
    const ch = chapter.value;
    if (!ch) return;
    try {
      await setPresence(worldSlug.value, ch.id, entity.id, place.id);
      await loadPresence(ch.id);
      analyseNow();
    } catch (e) {
      error.value = (e as Error).message;
    }
  },
  async create(word, kind) {
    await worldChange(() => createEntity(worldSlug.value, { name: word, kind, project: chapter.value?.project ?? null }));
    analyseNow();
  },
  async notAName(word) {
    await worldChange(() => fixes.notATypo(worldSlug.value, word));
    analyseNow();
  },
  async addSpelling(entity, word) {
    await worldChange(() => fixes.addSpelling(worldSlug.value, word, entity.id));
    analyseNow();
  },
  async summary(entity, text) {
    await worldChange(async () => {
      const { entity: e } = await getEntity(worldSlug.value, entity.id);
      await updateEntity(worldSlug.value, e, { summary: text });
    });
    analyseNow();
  },
  open: (entity) => void router.push({ name: "entity", params: { world: worldSlug.value, id: entity.id } }),
  async share(entity) {
    await worldChange(async () => {
      const { entity: e } = await getEntity(worldSlug.value, entity.id);
      await updateEntity(worldSlug.value, e, { project: null });
    });
    analyseNow();
  },
  addLabel: (entity, label) => void router.push({ name: "entity", params: { world: worldSlug.value, id: entity.id }, query: { add: label } }),
  async several(kind, label) {
    try {
      await setLabelSwitches(worldSlug.value, kind, label, { several: true });
      await cards.refresh(worldSlug.value);
      await afterWorldChange();
    } catch (e) {
      error.value = (e as Error).message;
    }
  },
  async endBefore(earlier, later) {
    try {
      await endBeforeRole(worldSlug.value, earlier, later);
      await cards.refresh(worldSlug.value);
      await afterWorldChange();
    } catch (e) {
      error.value = (e as Error).message;
    }
  },
  saveNote(text) {
    nextNote.value = text.trim();
    keepPlace();
  },
  stash: () => void openStash(),
  update: analyseNow,
  goBack() {
    const p = prose.value;
    const b = backIn.value;
    if (!p || !b) return;
    p.view.dispatch({ selection: { anchor: Math.min(b.cursor, p.view.state.doc.length) }, effects: EditorView.scrollIntoView(b.cursor, { y: "center" }) });
    p.view.focus();
    backIn.value = null;
  },
};
const companionHooks: NonNullable<WorldHooks["companion"]> = {
  revising: () => mode.value === "revising",
  marked: () =>
    (analysed?.findings ?? []).flatMap((f) => {
      const at = placeOf(f);
      return at ? [{ ...at, finding: f }] : [];
    }),
  drawn: (f) => prefs.editors[f.editor].inline && f.rule !== "near_miss",
  findingActions: (m) => {
    const f = m.finding;
    return {
      fix: f.fix ? { label: f.fix.label, run: () => applyFix(f, m) } : undefined,
      create: f.rule === "new_name" ? (kind) => panelActions.create(f.word!, kind) : undefined,
      notAName: f.rule === "new_name" ? () => panelActions.notAName(f.word!) : undefined,
      addSpelling: f.rule === "other_name" && f.a ? { name: f.a.name, run: () => panelActions.addSpelling(f.a!, f.word!) } : undefined,
      leave: ["echo", "long_sentence", "doubled"].includes(f.rule) ? () => panelActions.resolve(f.rule, f.key, "intentional") : undefined,
    };
  },
  stash: () => void openStash(),
  sceneBreak: () => {
    if (mode.value === "drafting") analyseNow();
  },
};

const editorStyle = computed(() => ({ "--prose-size": `${prefs.textSize}px`, "--prose-width": `${prefs.lineWidth}ch` }));
watch(title, (t) => {
  if (chapter.value && t.trim() && t !== chapter.value.title) saver?.edit({ title: t });
});

// ---- summary and status (docs/SPEC.md §11.2) ----
const statusList = ref<StatusRef[]>([]);
async function loadStatuses(ch: Chapter) {
  try {
    statusList.value = await statusApi.list(worldSlug.value, ch.project);
  } catch {
    // offline: the chapter's own status is all there is to show
    statusList.value = ch.status ? [ch.status] : [];
  }
}
async function setChapterAbout(about: { summary?: string; status_id?: string | null }) {
  const ch = chapter.value;
  if (!ch) return;
  error.value = "";
  try {
    const out = await setAbout(worldSlug.value, ch.id, about);
    if (chapter.value?.id === ch.id) chapter.value = { ...chapter.value, summary: out.summary, status: out.status };
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// ---- the cuts bin (docs/SPEC.md §11.3) ----
const cuts = ref<Cut[]>([]);
const toast = ref<{ label: string; undo: (() => Promise<void>) | null } | null>(null);
/** this chapter's cuts in the bin, and those still waiting on this device to be sent */
const panelCuts = computed(() => [
  ...outbox.cuts
    .filter((c) => c.chapterId === chapter.value?.id && !c.error)
    .map((c) => ({
      id: c.id, project: chapter.value?.project ?? null, body: c.body, before: c.before, after: c.after,
      words: countWords(storyText(c.body)), cut_at: c.cutAt, chapter: null, chapter_title: chapter.value?.title ?? "",
      put_back_at: null, put_back_to: null, match: null, waiting: true,
    }))
    .reverse(),
  ...cuts.value.filter((c) => !outbox.cuts.some((p) => p.id === c.id)),
]);
async function loadCuts(ch: Chapter) {
  try {
    const list = await chapterCuts(worldSlug.value, ch.id);
    if (chapter.value?.id === ch.id) cuts.value = list;
  } catch {
    /* reading the bin needs the network */
  }
}
// a cut made offline reached the server: the bin has it now
watch(
  () => outbox.cuts.length,
  (now, before) => {
    if (now < before && chapter.value) void loadCuts(chapter.value);
  },
);

/** Ctrl+Shift+X (or "Cut to bin"): the selection leaves the chapter and becomes a cut in the project's bin. */
async function cutToBin(from: number, to: number) {
  const p = prose.value;
  const ch = chapter.value;
  if (!p || !ch || readOnly.value) return;
  const doc = p.view.state.doc.toString();
  const text = doc.slice(from, to);
  if (!text.trim()) return;
  const { before, after } = around(doc, from, to);
  const id = crypto.randomUUID();
  p.view.dispatch({ changes: { from, to, insert: "" }, selection: { anchor: from }, userEvent: "delete.cut" });
  p.view.focus();
  // where the text was, as the chapter changes after this, for Undo
  const place = p.since();
  const sent = await outbox.addCut({ id, world: worldSlug.value, chapterId: ch.id, body: text, before, after });
  if (sent) void loadCuts(ch);
  toast.value = {
    label: cutLabel(countWords(storyText(text))),
    undo: async () => {
      const view = prose.value?.view;
      if (view && chapter.value?.id === ch.id) {
        const at = Math.min(place.map(from, -1), view.state.doc.length);
        view.dispatch({ changes: { from: at, insert: text }, selection: { anchor: at, head: at + text.length } });
      }
      try {
        if (!(await outbox.dropCut(id))) await removeCut(worldSlug.value, id);
      } catch {
        notice.value = "The text is back. The cut is still in the bin (no connection); you can leave it there.";
      }
      cuts.value = cuts.value.filter((c) => c.id !== id);
    },
  };
}

/** Put a cut back: where it was (found by the text around it) or at the cursor. An ordinary edit (Ctrl+Z undoes
 * it); the cut stays in the bin, marked put back. From Salvage, a place that can't be found means the end. */
async function putBack(cut: Cut, where: "place" | "cursor", fromSalvage = false) {
  const p = prose.value;
  const ch = chapter.value;
  if (!p || !ch || readOnly.value) return;
  const doc = p.view.state.doc.toString();
  const found = where === "place" ? findPlace(doc, cut.before, cut.after) : null;
  const at = found ?? (fromSalvage ? doc.length : p.view.state.selection.main.head);
  const text = fromSalvage && found === null && doc && !doc.endsWith("\n") ? `\n\n${cut.body}` : cut.body;
  p.view.dispatch({
    changes: { from: at, insert: text },
    selection: { anchor: at + text.length },
    effects: EditorView.scrollIntoView(at, { y: "center" }),
    userEvent: "input.paste",
  });
  p.view.focus();
  notice.value =
    where === "place" && found === null
      ? `Couldn't find where it was taken from, so it went in at ${fromSalvage ? "the end" : "the cursor"}.`
      : "Put back. Ctrl+Z takes it out again; the bin keeps a copy, marked put back.";
  try {
    await markPutBack(worldSlug.value, cut.id, ch.id);
  } catch {
    notice.value += " (The bin will still list it: no connection.)";
  }
  void loadCuts(ch);
}
async function copyCut(cut: Cut) {
  try {
    await navigator.clipboard.writeText(cut.body.trim());
    notice.value = "Copied.";
  } catch {
    error.value = "Couldn't copy here; select the text in the bin instead.";
  }
}

// ---- changes since a checkpoint (docs/SPEC.md §11.6): chosen by label, remembered per project on this device ----
const sinceLabel = ref("");
const sinceLabels = ref<string[]>([]);
const sinceLine = ref("");
let sinceBase: string | null = null;
let sinceCheckpoints: Checkpoint[] = [];
let sinceTimer = 0;
const sinceKey = (ch: Chapter) => `quarry.since.${worldSlug.value}/${ch.project}`;
function readSince(ch: Chapter): string {
  try {
    return localStorage.getItem(sinceKey(ch)) ?? "";
  } catch {
    return "";
  }
}
async function loadSince(ch: Chapter) {
  sinceLabel.value = readSince(ch);
  try {
    sinceCheckpoints = (await labelledCheckpoints(worldSlug.value, ch.id)).list;
  } catch {
    sinceCheckpoints = [];
  }
  if (chapter.value?.id !== ch.id) return;
  sinceLabels.value = [...new Set(sinceCheckpoints.map((c) => c.label))];
  await resolveSince(ch);
}
async function resolveSince(ch: Chapter) {
  sinceBase = null;
  sinceLine.value = "";
  const label = sinceLabel.value;
  const cp = label ? sinceCheckpoints.find((c) => c.label === label) : undefined;
  if (label && !cp) sinceLine.value = `This chapter has no checkpoint “${label}”.`;
  if (cp) {
    const body = await checkpointBody(worldSlug.value, ch.id, cp).catch(() => null);
    if (chapter.value?.id !== ch.id) return;
    if (body === null) sinceLine.value = `The checkpoint “${label}” isn't on this device yet; it is fetched when you're online.`;
    sinceBase = body;
  }
  showChanges();
}
function chooseSince(label: string) {
  const ch = chapter.value;
  if (!ch) return;
  try {
    if (label) localStorage.setItem(sinceKey(ch), label);
    else localStorage.removeItem(sinceKey(ch));
  } catch {
    /* not remembered, but shown now */
  }
  sinceLabel.value = label;
  void resolveSince(ch);
}
/** Work out the changes since the checkpoint for the text as it is now (only while Revising). */
function showChanges() {
  clearTimeout(sinceTimer);
  const p = prose.value;
  if (!p) return;
  if (mode.value !== "revising" || sinceBase === null || readOnly.value) {
    p.setChanges(null);
    return;
  }
  const started = performance.now();
  const c = changesSince(sinceBase, p.view.state.doc.toString());
  performance.measure("quarry:changes", { start: started });
  p.setChanges(c.changes);
  sinceLine.value = changesLine(c, sinceLabel.value);
}
/** Again when typing pauses, as the Revising findings are; nothing per keystroke. */
function scheduleChanges() {
  if (sinceBase === null || mode.value !== "revising") return;
  clearTimeout(sinceTimer);
  sinceTimer = window.setTimeout(showChanges, 700);
}
const since = computed(() => ({ labels: sinceLabels.value, chosen: sinceLabel.value, line: sinceLine.value, revising: mode.value === "revising" }));

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
  if (label.value.trim() && chapter.value) void loadSince(chapter.value);
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
    if (!unreachable(e)) throw e;
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
  void loadSince(ch);
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
          <span v-if="!readOnly" class="mode-switch" role="group" aria-label="Mode" data-testid="mode">
            <button type="button" :class="{ on: mode === 'drafting' }" :aria-pressed="mode === 'drafting'" title="Names coloured, nothing else marked; findings wait for a break" @click="mode = 'drafting'">Drafting</button>
            <button type="button" :class="{ on: mode === 'revising' }" :aria-pressed="mode === 'revising'" title="Findings marked in the text as they're found" @click="mode = 'revising'">Revising</button>
          </span>
          <label class="toggle"><input v-model="focusMode" type="checkbox" /> Focus</label>
          <label class="toggle desk-only"><input v-model="typewriter" type="checkbox" /> Typewriter</label>
          <button type="button" class="btn btn-sm desk-only" :aria-pressed="showPanel" @click="showPanel = !showPanel">Panel</button>
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

      <form v-if="stashing" class="checkpoint-bar" @submit.prevent="keepThought">
        <label for="stash-thought">A thought for later (to the inbox, tied to this chapter)</label>
        <input id="stash-thought" ref="stashBox" v-model="thought" type="text" maxlength="2000" @keydown.esc="(stashing = false), prose?.view.focus()" />
        <button class="btn btn-sm btn-primary" type="submit">Stash</button>
      </form>
      <form v-if="leaving" class="checkpoint-bar leave-bar" data-testid="leave-note" @submit.prevent="finishLeave(true)">
        <label for="leave-note">Before you go: what's next here?</label>
        <input id="leave-note" ref="leaveBox" v-model="leaveNote" type="text" maxlength="2000" placeholder="A note for next time" />
        <button class="btn btn-sm btn-primary" type="submit">Save and go</button>
        <button class="btn btn-sm" type="button" @click="finishLeave(false)">Skip</button>
      </form>

      <div class="title-wrap">
        <input v-model="title" class="chapter-title" aria-label="Chapter title" maxlength="300" :readonly="readOnly" />
      </div>
      <div ref="host" class="editor-host" :class="{ focus: focusMode }" :style="editorStyle" data-testid="editor" />
    </div>

    <CompanionPanel
      v-if="chapter && !showHistory && showPanel && !focusMode"
      :findings="findings"
      :checks="chapterChecks"
      :items="items"
      :note="nextNote"
      :back-in="backIn"
      :drafting="mode === 'drafting'"
      :stale="stale"
      :types="cards.types"
      :world="world.slug"
      :actions="panelActions"
      @dismiss-back="backIn = null"
      @tab="onTab"
    >
      <ChapterSide
        :world="world.slug"
        :chapter="chapter"
        :names="names"
        :read-only="readOnly"
        :presence="presence"
        :statuses="statusList"
        :cuts="panelCuts"
        :since="since"
        @pov="setPov"
        @checkpoint="checkpoint"
        @experiment="experiment"
        @retire="closing = 'retire'"
        @about="setChapterAbout"
        @put-back="(c, where) => putBack(c, where)"
        @copy="copyCut"
        @since="chooseSince"
      />
    </CompanionPanel>
    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" @dismiss="toast = null" />

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
