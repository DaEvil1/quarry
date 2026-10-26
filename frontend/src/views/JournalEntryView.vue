<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { EditorView } from "@codemirror/view";

import { del, unreachable } from "../api";
import { blankPictures } from "../pictures";
import { addRelationship, createEntity, fixes, getEntity, setLabelSwitches, typeOptions, updateEntity } from "../bible";
import CompanionPanel from "../components/CompanionPanel.vue";
import HistoryPanel from "../components/HistoryPanel.vue";
import JournalSide from "../components/JournalSide.vue";
import UndoToast from "../components/UndoToast.vue";
import { linkedPairs, resolutions, resolve as resolveApi, type PanelActions } from "../companion";
import { itemBody, passageActions, type PassageContext } from "../editor/passage";
import { createProse, countWords, type Prose, type WorldHooks } from "../editor/prose";
import { editorPictureHooks } from "../editor/pictureHooks";
import PicturePicker from "../components/PicturePicker.vue";
import type { Picture } from "../pictures";
import { ChapterSaver, type SaveStatus } from "../editor/saver";
import type { HistoryActions } from "../editor/strips";
import { recordEvent, undoRecord } from "../history";
import {
  deleteEntry,
  entryItems,
  entryNote,
  saveEntryNote,
  sinceThis,
  type SinceThis,
  entryTies,
  getEntry,
  journalDay,
  restoreEntry,
  saveEntry,
  setEntryAbout,
  snapshotEntry,
} from "../journal";
import { cacheEntry, dropDraft, getDraft, localEntry, queueRevision, saveDraft, sendPendingEntries } from "../offline";
import { usePrefs } from "../prefs";
import { useOutbox } from "../stores/outbox";
import { useSession } from "../stores/session";
import type { EntityRef, JournalDetail } from "../types";
import { kindsOf, useCards } from "../world/cards";
import { analyse, linkKey, type Finding } from "../world/findings";
import { unitOf } from "../world/when";
import NotFoundView from "./NotFoundView.vue";

// A journal entry in the chapter editor (docs/SPEC.md §14.1.1): names coloured, cards, the quick-fix strip, F8,
// recording from a passage (as planned, planned in this entry), autosave with revisions and History, and the offline
// copy. What stays with chapters (point of view, times, "is at", cuts, experiments, margin notes, the Continuity tab)
// isn't here.

const route = useRoute();
const router = useRouter();
const session = useSession();
const prefs = usePrefs();
const cards = useCards();
const outbox = useOutbox();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const entry = ref<JournalDetail | null>(null);
const missing = ref(false);
const title = ref("");
const day = ref("");
const words = ref(0);
const status = ref<SaveStatus>("saved");
const notice = ref("");
const error = ref("");
// a picture on its way in (docs/SPEC.md §17.3), at the foot
const pictureStatus = ref<{ text: string; error: boolean } | null>(null);
const pickingPicture = ref(false);
const host = ref<HTMLElement | null>(null);
const prose = shallowRef<Prose | null>(null);
const offlineCopy = ref(false);
const focusMode = ref(prefs.focusMode);
const typewriter = ref(prefs.typewriter);
const showHistory = ref(false);
const showPanel = ref(prefs.panel);
const mode = ref(prefs.mode);
let saver: ChapterSaver<JournalDetail> | null = null;
let draftTimer: ReturnType<typeof setTimeout> | undefined;
let countTimer = 0;

const STATUS_TEXT: Record<SaveStatus, string> = {
  saved: "Saved",
  unsaved: "Not saved yet",
  saving: "Saving…",
  offline: "Offline: kept here, retrying",
  conflict: "Changed elsewhere: your text is in History",
};
const projectName = computed(() => world.value?.projects.find((p) => p.slug === entry.value?.project)?.name ?? "Whole world");

function countLater(text: string) {
  clearTimeout(countTimer);
  countTimer = window.setTimeout(() => (words.value = countWords(blankPictures(text))), 300);
}
function keepDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    const e = entry.value;
    const body = prose.value?.view.state.doc.toString();
    if (!e || body === undefined || !saver) return;
    void saveDraft({ chapterId: e.id, doc: "journal", world: worldSlug.value, title: title.value, body, baseVersion: saver.currentVersion });
  }, 400);
}

// ---- cards as of a chapter or a time; the end of the story when nothing is chosen (kept per entry on the device) ----
const asOfKey = (id: string) => `quarry.asof.journal.${id}`;
const asOf = ref<{ asof?: string; at?: number }>({});
function readAsOf(id: string) {
  try {
    asOf.value = JSON.parse(localStorage.getItem(asOfKey(id)) ?? "{}") as { asof?: string; at?: number };
  } catch {
    asOf.value = {};
  }
}
function setAsOf(choice: { asof?: string; at?: number }) {
  asOf.value = choice;
  try {
    if (entry.value) localStorage.setItem(asOfKey(entry.value.id), JSON.stringify(choice));
  } catch {
    /* shown now, not remembered */
  }
  prose.value?.refreshNames();
}
const readAt = () => (asOf.value.at !== undefined ? { time: asOf.value.at } : (asOf.value.asof ?? null));

// ---- the matcher, rebuilt when the cards change ----
let matcher = cards.matcher();
let matcherVersion = cards.version;
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
watch(() => cards.pictures, () => prose.value?.refreshPictures());
function pickedPicture(p: Picture) {
  pickingPicture.value = false;
  cards.putPicture(p);
  prose.value?.insertPicture(p.id);
}
function uploadPictures(files: File[]) {
  pickingPicture.value = false;
  void prose.value?.addPictures(files);
}

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
/** a new entry made from a journal entry starts in its project's bible when the world has several (§12.4) */
const newEntryProject = () => ((world.value?.projects.length ?? 0) > 1 ? (entry.value?.project ?? null) : null);

/** The entries named in a passage, by the matcher that colours names, in order. A shared name counts as the choice
 * lines above the passage settle it, and not at all where none does (docs/SPEC.md §14.10). */
function namedIn(raw: string): EntityRef[] {
  const m = currentMatcher();
  const out: EntityRef[] = [];
  const doc = prose.value?.view.state.doc.toString() ?? "";
  const at = doc.indexOf(raw);
  const choices = at >= 0 ? m.choices(doc) : [];
  let from = Math.max(at, 0);
  for (const line of raw.split("\n")) {
    for (const h of m.resolve(m.scanLine(line, from, false), choices)) {
      if (h.kind === "near_miss" || h.kind === "ambiguous") continue;
      for (const id of h.chosen ?? [h.entityId]) {
        const c = cards.byId.get(id);
        if (c && !out.some((x) => x.id === id)) out.push({ id: c.id, name: c.name, kind: c.kind });
      }
    }
    from += line.length + 1;
  }
  return out;
}

const worldHooks: WorldHooks = {
  matcher: currentMatcher,
  // as of the end of the story (or the chapter or time chosen), with planned facts, marked
  card: (id) => cards.inPlanning(cards.byId.get(id), readAt()),
  names: () => cards.names,
  prefs: () => prefs.$state,
  pictures: editorPictureHooks(() => worldSlug.value, (text, failed) => (pictureStatus.value = text ? { text, error: !!failed } : null), () => prose.value?.refreshPictures()),
  open: (id) => void router.push({ name: "entity", params: { world: worldSlug.value, id } }),
  addName: (id, word) => worldChange(() => fixes.addSpelling(worldSlug.value, word, id)),
  notATypo: (word) => worldChange(() => fixes.notATypo(worldSlug.value, word)),
  create: (name, kind) => worldChange(() => createEntity(worldSlug.value, { name, kind, project: newEntryProject() })),
  exclude: (id, phrase) =>
    worldChange(async () => {
      const { entity } = await getEntity(worldSlug.value, id);
      await updateEntity(worldSlug.value, entity, { exclusions: [...entity.exclusions, phrase] });
    }),
  get companion() {
    return companionHooks;
  },
  several: (kind, label) => cards.several(kind, label),
  noIsAt: true,
  isAt: () => ({ here: () => null, places: () => [], set: async () => undefined }),
  // Link to… from a card here records the relationship as planned, planned in this entry
  link: (id) => ({
    names: () => cards.names,
    options: (other) => {
      // any of each one's kinds (docs/SPEC.md §14.8)
      const me = cards.byId.get(id);
      const them = cards.byId.get(other.id);
      return typeOptions(cards.types, me ? kindsOf(me) : ["other"], them ? kindsOf(them) : [other.kind]).map((o) => ({ key: `${o.type.id}|${o.forward}`, reads: o.reads }));
    },
    add: (other, key) => {
      const [typeId, forward] = key.split("|");
      const [a, b] = forward === "true" ? [id, other.id] : [other.id, id];
      return worldChange(() => addRelationship(worldSlug.value, { type_id: typeId!, a_id: a, b_id: b, standing: "planned", planned_in_journal_id: entry.value?.id ?? null }));
    },
  }),
  history: (_from, _to, raw) => historyActions(raw),
  passage: (_from, _to, raw) => passageActions(passageContext(), raw),
};

// ---- Record as event from the Journal: participants planned, the passage a note (docs/SPEC.md §14.1.2) ----
function historyActions(raw: string): HistoryActions {
  const e = entry.value!;
  const passage = raw.trim();
  const named = namedIn(raw);
  return {
    named,
    events: () => {
      const events = cards.names.filter((n) => cards.hasKind(n.id, "event"));
      return [...events].sort((a, b) => Number(!named.some((n) => n.id === a.id)) - Number(!named.some((n) => n.id === b.id)));
    },
    relatedTo: (eventId) => new Set((cards.byId.get(eventId)?.relations ?? []).map((r) => r.other.id)),
    eventWhen: (eventId) => {
      const c = cards.byId.get(eventId);
      return c?.whenText ? { text: c.whenText, at: c.when?.at ?? null } : null;
    },
    chapterTime: null,
    untimed: false,
    record: async (r) => {
      try {
        const done = await recordEvent(worldSlug.value, {
          event_id: r.eventId,
          name: r.name,
          journal_id: e.id,
          passage,
          taking: r.taking.map((x) => ({ entity_id: x.id, role: x.role })),
          when: r.when ? { time_at: r.when.at, time_approx: r.when.approx } : null,
          time_choice: r.choice,
        });
        await cards.refresh(worldSlug.value);
        toast.value = {
          label: `Recorded “${done.event.name}” · ${r.taking.length} taking part, planned`,
          undo: async () => {
            await undoRecord(worldSlug.value, done);
            await cards.refresh(worldSlug.value);
          },
          actions: [{ label: "Open", run: () => router.push({ name: "entity", params: { world: worldSlug.value, id: done.event_id } }) }],
        };
      } catch (err) {
        error.value = (err as Error).message;
      }
    },
    // there is no "here" in the Journal: no born here or died here
    setLife: async () => undefined,
    setChapterTime: () => undefined,
  };
}

// ---- record a fact, spark or question from a passage ----
let lastItem: string | null = null;
async function addItem(i: { kind: "spark" | "question" | "task"; body: string; entities: string[]; passage: string; status: "open" | "deferred" }) {
  const e = entry.value!;
  const id = crypto.randomUUID();
  lastItem = id;
  const sent = await outbox.add({ id, world: worldSlug.value, body: i.body, kind: i.kind, project: e.project, source: "passage", journalId: e.id, passage: i.passage, status: i.status, entities: i.entities });
  if (sent) void loadItems(e.id);
  return { sent };
}
function itemSaved(kind: string, sent: boolean) {
  const id = lastItem;
  toast.value = {
    label: `${kind[0]!.toUpperCase()}${kind.slice(1)} saved${sent ? "" : " on this device; it goes to the inbox when you're back online"}`,
    undo: id
      ? async () => {
          if (!(await outbox.dropCapture(id))) await del(`/api/worlds/${encodeURIComponent(worldSlug.value)}/items/${id}`);
          if (entry.value) void loadItems(entry.value.id);
        }
      : null,
    actions: sent && id ? [{ label: "Open", run: () => router.push({ name: "item", params: { world: worldSlug.value, id } }) }] : [],
  };
}
function passageContext(): PassageContext {
  const e = entry.value!;
  return {
    world: worldSlug.value,
    where: "journal",
    sourceId: e.id,
    project: e.project,
    names: () => cards.names,
    namedIn,
    addItem,
    recorded: (r) => {
      void cards.refresh(worldSlug.value).then(analyseNow);
      toast.value = {
        label: `Recorded “${r.label}${r.value ? `: ${r.value}` : ""}” on ${r.entity.name}`,
        undo: async () => {
          await r.undo();
          await cards.refresh(worldSlug.value);
        },
        actions: [{ label: "Open", run: () => router.push({ name: "entity", params: { world: worldSlug.value, id: r.entity.id } }) }],
      };
    },
    saved: itemSaved,
    failed: (m) => (error.value = m),
  };
}

// ---- the note for next time (docs/SPEC.md §14.4), and since this was written (§14.5) ----
const nextNote = ref("");
const backIn = ref<{ context: string; note: string; cursor: number } | null>(null);
const since = ref<SinceThis | null>(null);
async function loadNote(e: JournalDetail) {
  const [note, s] = await Promise.allSettled([entryNote(worldSlug.value, e.id), sinceThis(worldSlug.value, e.id)]);
  if (entry.value?.id !== e.id) return;
  if (s.status === "fulfilled") since.value = s.value;
  if (note.status !== "fulfilled") return;
  nextNote.value = note.value.note;
  const body = prose.value?.view.state.doc.toString() ?? e.body;
  if (note.value.note || (note.value.cursor > 0 && note.value.cursor <= body.length)) {
    const at = Math.min(note.value.cursor, body.length);
    const start = body.lastIndexOf("\n", at - 1) + 1;
    const context = body.slice(Math.max(start, at - 60), at).trim();
    backIn.value = context || note.value.note ? { context, note: note.value.note, cursor: at } : null;
  }
}
/** Where the writer is, and their note, kept for next time (best effort: offline it waits for the next visit). */
function keepPlace() {
  const e = entry.value;
  const p = prose.value;
  if (!e || !p) return;
  void saveEntryNote(worldSlug.value, e.id, nextNote.value, p.view.state.selection.main.head).catch(() => {});
}
function saveNote(text: string) {
  nextNote.value = text.trim();
  keepPlace();
}
// leaving an entry after writing 30 words or more: a note for next time, asked once and skippably, as for chapters
let wordsAtOpen = 0;
let asked = false;
const leaving = ref<string | null>(null);
const leaveNote = ref("");
const leaveBox = ref<HTMLInputElement | null>(null);
async function finishLeave(save: boolean) {
  if (save) nextNote.value = leaveNote.value.trim();
  const target = leaving.value;
  leaving.value = null;
  if (target) await router.push(target);
}

// ---- the companion: Proofreader, Connections (Record how: planned), Archivist, Loose ends; no Continuity ----
const findings = shallowRef<Finding[]>([]);
let analysed: { since: ReturnType<Prose["since"]>; findings: Finding[] } | null = null;
const stale = ref(false);
const linked = ref(new Set<string>());
const resolved = ref(new Set<string>());
const items = ref<{ id: string; title: string | null; body: string; passage: string | null }[]>([]);
let analyseTimer = 0;
function analyseNow() {
  clearTimeout(analyseTimer);
  const p = prose.value;
  const e = entry.value;
  if (!p || !e) return;
  analysed = {
    since: p.since(),
    findings: analyse({
      text: p.view.state.doc.toString(),
      matcher: currentMatcher(),
      card: (id) => cards.byId.get(id),
      linked: linked.value,
      presence: [],
      resolved: resolved.value,
      longSentence: prefs.longSentence,
      project: e.project ?? undefined,
      projectName: (slug) => world.value?.projects.find((x) => x.slug === slug)?.name ?? slug,
      expected: (kind) => cards.expected(kind),
      journal: true,
    }).filter((f) => prefs.editors[f.editor].on && f.editor !== "continuity"),
  };
  findings.value = analysed.findings;
  stale.value = false;
  p.setMarks();
}
function scheduleAnalysis() {
  stale.value = true;
  if (mode.value !== "revising") return;
  clearTimeout(analyseTimer);
  analyseTimer = window.setTimeout(analyseNow, 700);
}
function placeOf(f: { from?: number; to?: number }): { from: number; to: number } | null {
  if (!analysed || f.from === undefined || f.to === undefined) return null;
  const from = analysed.since.map(f.from, 1);
  const to = analysed.since.map(f.to, -1);
  return to - from === f.to - f.from ? { from, to } : null;
}
function applyFix(f: Finding, at: { from: number } | null = placeOf(f)) {
  const p = prose.value;
  if (!p || !f.fix || f.from === undefined || !at) {
    analyseNow();
    return;
  }
  const d = at.from - f.from;
  p.view.dispatch({ changes: { from: f.fix.from + d, to: f.fix.to + d, insert: f.fix.insert } });
  analyseNow();
}
async function loadItems(id: string) {
  items.value = await entryItems(worldSlug.value, id).catch(() => items.value);
}
async function loadCompanion(e: JournalDetail) {
  const [pairs, res] = await Promise.allSettled([linkedPairs(worldSlug.value), resolutions(worldSlug.value)]);
  if (entry.value?.id !== e.id) return;
  if (pairs.status === "fulfilled") linked.value = pairs.value;
  if (res.status === "fulfilled") resolved.value = new Set(res.value.map((r) => `${r.rule}|${r.key}`));
  void loadItems(e.id);
  analyseNow();
}

// "Make a question" on a TK or ?? line
const asking = ref<{ passage: string } | null>(null);
const askLine = ref("");
const askPark = ref(false);
const askBox = ref<HTMLInputElement | null>(null);
async function keepQuestion() {
  const a = asking.value;
  asking.value = null;
  if (!a) return;
  try {
    const { sent } = await addItem({ kind: "question", body: itemBody(askLine.value, a.passage), entities: namedIn(a.passage).map((n) => n.id), passage: a.passage, status: askPark.value ? "deferred" : "open" });
    itemSaved("question", sent);
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// stash a thought: to the inbox, tied to this entry
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
  const e = entry.value;
  stashing.value = false;
  prose.value?.view.focus();
  if (!text || !e) return;
  const sent = await outbox.add({ world: worldSlug.value, body: text, kind: "spark", project: e.project, source: "stash", journalId: e.id });
  notice.value = sent ? "Stashed in the inbox." : "Stashed on this device; it goes to the inbox when you're back online.";
  if (sent) void loadItems(e.id);
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
      analyseNow();
    } catch (e) {
      error.value = (e as Error).message;
    }
  },
  // Record how: planned, planned in this entry
  async link(a, b, typeId, forward) {
    const [x, y] = forward ? [a, b] : [b, a];
    await worldChange(() => addRelationship(worldSlug.value, { type_id: typeId, a_id: x.id, b_id: y.id, standing: "planned", planned_in_journal_id: entry.value?.id ?? null }));
    linked.value = new Set([...linked.value, linkKey(a.id, b.id)]);
    analyseNow();
  },
  isAt: () => undefined,
  async create(word, kind) {
    await worldChange(() => createEntity(worldSlug.value, { name: word, kind, project: newEntryProject() }));
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
    await worldChange(() => setLabelSwitches(worldSlug.value, kind, label, { several: true }));
    analyseNow();
  },
  endBefore: () => undefined,
  reAnchor: () => undefined,
  saveNote: (text) => saveNote(text),
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
  question: (f) => {
    const text = prose.value?.view.state.doc.toString() ?? "";
    const at = placeOf(f);
    if (!at) return;
    const start = text.lastIndexOf("\n", at.from - 1) + 1;
    const end = text.indexOf("\n", at.from);
    asking.value = { passage: text.slice(start, end < 0 ? text.length : end).trim() };
    askLine.value = "";
    askPark.value = false;
    void nextTick(() => askBox.value?.focus());
  },
  showPassage: (passage) => void prose.value?.markPassage(passage),
};
const companionHooks: NonNullable<WorldHooks["companion"]> = {
  revising: () => mode.value === "revising",
  choicesOnly: true,
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
const panelTab = ref("chapter");
function onTab(t: string) {
  panelTab.value = t;
  if (mode.value === "drafting") analyseNow();
}
watch(mode, (m) => {
  prefs.set("mode", m);
  analyseNow();
});
watch(showPanel, (on) => {
  prefs.set("panel", on);
  if (on && mode.value === "drafting") analyseNow();
});
watch(focusMode, (on) => {
  prose.value?.setFocusMode(on);
  prefs.set("focusMode", on);
});
watch(typewriter, (on) => {
  prose.value?.setTypewriter(on);
  prefs.set("typewriter", on);
});

// ---- loading, saving, leaving ----
function mount(e: JournalDetail) {
  prose.value?.destroy();
  saver?.close();
  words.value = countWords(blankPictures(e.body));
  wordsAtOpen = words.value;
  asked = false;
  if (!host.value) return;
  prose.value = createProse(host.value, {
    doc: e.body,
    placeholderText: "What does the story want right now?",
    onChange: (text) => {
      countLater(text);
      saver?.edit({ body: text });
      keepDraft();
      scheduleAnalysis();
    },
    onSave: () => void checkpoint(),
    world: worldHooks,
  });
  prose.value.view.contentDOM.setAttribute("aria-label", "Journal entry text");
  prose.value.setFocusMode(focusMode.value);
  prose.value.setTypewriter(typewriter.value);
  saver = new ChapterSaver<JournalDetail>(e, {
    // an entry made offline is sent first
    save: async (v, changes) => {
      await sendPendingEntries(worldSlug.value, e.id);
      return saveEntry(worldSlug.value, e.id, v, changes);
    },
    snapshot: (reason, extra) => snapshotEntry(worldSlug.value, e.id, reason, extra),
    now: () => Date.now(),
  }, {
    saved: (saved, sentBody) => {
      const current = prose.value?.view.state.doc.toString();
      entry.value = { ...saved, body: current ?? saved.body };
      offlineCopy.value = false;
      void cacheEntry(worldSlug.value, saved);
      void dropDraft(saved.id, sentBody);
    },
    conflict: (current) => {
      entry.value = current;
      void dropDraft(current.id);
      void cacheEntry(worldSlug.value, current);
      prose.value?.replaceDoc(current.body);
      saver?.rebase(current);
      notice.value = "This entry was changed on another device. Its text is shown now; yours was kept in History as a conflict copy.";
    },
    status: (s) => (status.value = s),
  });
}

async function load() {
  missing.value = false;
  offlineCopy.value = false;
  const id = String(route.params.id);
  let e: JournalDetail | undefined;
  try {
    e = await getEntry(worldSlug.value, id);
    void cacheEntry(worldSlug.value, e);
  } catch (err) {
    // offline, or an entry made on this device that the server hasn't got yet
    e = await localEntry(id);
    offlineCopy.value = !!e && unreachable(err);
  }
  if (!e) {
    missing.value = true;
    return;
  }
  // the head shows once the entry is here: what it says first, so nothing typed into it is overwritten
  title.value = e.title ?? "";
  day.value = e.entry_date;
  entry.value = e;
  toast.value = null;
  readAsOf(e.id);
  await nextTick();
  mount(e);
  await recoverDraft(e);
  void loadCompanion(e);
  void loadNote(e);
  openAt();
}

/** Opened at a place (a passage, from where something was planned, an item, the planning reading). */
function openAt() {
  const p = prose.value;
  if (!p) return;
  const passage = typeof route.query.passage === "string" ? route.query.passage : "";
  if (passage) {
    if (!p.markPassage(passage, true)) notice.value = "That passage has changed since; the entry opens at the top.";
    return;
  }
  const at = typeof route.query.at === "string" ? Number(route.query.at) : NaN;
  if (Number.isFinite(at)) {
    const pos = Math.max(0, Math.min(at, p.view.state.doc.length));
    p.view.dispatch({ selection: { anchor: pos }, effects: EditorView.scrollIntoView(pos, { y: "center" }) });
    p.view.focus();
  }
}

async function recoverDraft(e: JournalDetail) {
  const draft = await getDraft(e.id);
  if (!draft || (draft.body === e.body && draft.title === (e.title ?? ""))) {
    if (draft) void dropDraft(e.id);
    return;
  }
  if (draft.baseVersion === e.version) {
    prose.value?.replaceDoc(draft.body);
    if (draft.title && draft.title !== title.value) title.value = draft.title;
    notice.value = "Text from this device that wasn't saved yet is back in the editor.";
    return;
  }
  const label = "Written on this device while another version was saved";
  try {
    await snapshotEntry(worldSlug.value, e.id, "conflict", { body: draft.body, label });
  } catch {
    await queueRevision({ world: worldSlug.value, chapterId: e.id, doc: "journal", reason: "conflict", label, body: draft.body });
  }
  await dropDraft(e.id);
  notice.value = "This entry changed elsewhere since this device last wrote in it. That text is kept in History as a conflict copy.";
}

function onHide() {
  if (document.visibilityState === "hidden") {
    keepPlace();
    void saver?.leave();
  }
}
function onUnload(ev: BeforeUnloadEvent) {
  if (saver?.dirty) {
    void saver.flush();
    ev.preventDefault();
  }
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
  if (!asked && prefs.askNote && entry.value && words.value - wordsAtOpen >= 30) {
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

watch(title, (t) => {
  if (entry.value && t !== (entry.value.title ?? "")) saver?.edit({ title: t });
});
/** the date and the project: labels, saved without the version check */
async function setAbout(about: { entry_date?: string; project?: string | null }) {
  const e = entry.value;
  if (!e) return;
  error.value = "";
  try {
    const out = await setEntryAbout(worldSlug.value, e.id, about);
    entry.value = { ...e, entry_date: out.entry_date, project: out.project };
    day.value = out.entry_date;
  } catch (err) {
    error.value = unreachable(err) ? "The date and project need the network; try again when you're back online." : (err as Error).message;
  }
}

// ---- checkpoint, History, deleting ----
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
async function restore(revisionId: string, body: string) {
  const e = entry.value;
  if (!e) return;
  await saver?.flush();
  let out: JournalDetail;
  try {
    out = await restoreEntry(worldSlug.value, e.id, revisionId);
  } catch (err) {
    if (!unreachable(err)) throw err;
    const current = prose.value?.view.state.doc.toString() ?? "";
    await queueRevision({ world: worldSlug.value, chapterId: e.id, doc: "journal", reason: "restore", label: "Before restoring an older version (offline)", body: current });
    showHistory.value = false;
    prose.value?.replaceDoc(body);
    notice.value = "Restored on this device. It's saved when you're back online; the text it replaced is kept.";
    return;
  }
  entry.value = out;
  showHistory.value = false;
  prose.value?.replaceDoc(out.body);
  title.value = out.title ?? "";
  saver?.rebase(out);
  notice.value = "Restored. The text it replaced is in History.";
}
const deleting = ref<string | null>(null);
async function askDelete() {
  const e = entry.value;
  if (!e) return;
  try {
    const t = await entryTies(worldSlug.value, e.id);
    const parts = [
      t.facts ? `${t.facts} fact${t.facts === 1 ? "" : "s"}` : "",
      t.relationships ? `${t.relationships} relationship${t.relationships === 1 ? "" : "s"}` : "",
      t.notes ? `${t.notes} event note${t.notes === 1 ? "" : "s"}` : "",
    ].filter(Boolean);
    const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
    deleting.value = list ? `${list} ${parts.length === 1 && !list.endsWith("s") ? "was" : "were"} planned in this entry. They keep their passage, without the entry.` : "Nothing was planned in this entry.";
  } catch (err) {
    error.value = (err as Error).message;
  }
}
async function confirmDelete() {
  const e = entry.value;
  if (!e) return;
  saver?.close();
  await deleteEntry(worldSlug.value, e.id);
  void dropDraft(e.id);
  await router.push({ name: "journal", params: { world: worldSlug.value } });
}

const toast = ref<{ label: string; undo: (() => Promise<void>) | null; actions?: { label: string; run: () => unknown }[] } | null>(null);
// while Revising, a mark in the margin beside each passage with an open item (docs/SPEC.md §14.3.1)
watch(
  () => [mode.value, items.value, prose.value] as const,
  ([m, list, p]) => p?.setItemMarks(m === "revising" ? list.flatMap((i) => (i.passage ? [i.passage] : [])) : null),
);
const editorStyle = computed(() => ({ "--prose-size": `${prefs.textSize}px`, "--prose-width": `${prefs.lineWidth}ch` }));
const unit = computed(() => unitOf(world.value));
</script>

<template>
  <NotFoundView v-if="!world || missing" what="journal entry" />
  <div v-else class="chapter-page journal-page" :class="{ 'with-history': showHistory }">
    <div class="chapter-main">
      <div class="chapter-bar">
        <div class="crumbs">
          <RouterLink :to="{ name: 'journal', params: { world: world.slug } }">Journal</RouterLink>
          <template v-if="entry"> · {{ journalDay(entry.entry_date) }}</template>
        </div>
        <div class="chapter-tools">
          <span class="muted small" data-testid="save-status" :class="`status-${status}`">{{ STATUS_TEXT[status] }}</span>
          <span class="muted small" data-testid="word-count">{{ words.toLocaleString() }} words</span>
          <span class="mode-switch" role="group" aria-label="Mode" data-testid="mode">
            <button type="button" :class="{ on: mode === 'drafting' }" :aria-pressed="mode === 'drafting'" @click="mode = 'drafting'">Drafting</button>
            <button type="button" :class="{ on: mode === 'revising' }" :aria-pressed="mode === 'revising'" @click="mode = 'revising'">Revising</button>
          </span>
          <label class="toggle"><input v-model="focusMode" type="checkbox" /> Focus</label>
          <label class="toggle desk-only"><input v-model="typewriter" type="checkbox" /> Typewriter</label>
          <button type="button" class="btn btn-sm desk-only" :aria-pressed="showPanel" @click="showPanel = !showPanel">Panel</button>
          <button type="button" class="btn btn-sm" title="Put in a picture: one of the world's, or upload one" data-testid="picture-button" @click="pickingPicture = true">Picture…</button>
          <button type="button" class="btn btn-sm" @click="showHistory = !showHistory">History</button>
        </div>
      </div>

      <div v-if="offlineCopy" class="notice offline small" role="status" data-testid="offline-copy">
        Offline: this is the copy on this device. What you write is kept here and saved when you're back.
      </div>
      <div v-if="notice" class="notice ok small" role="status" @click="notice = ''">{{ notice }}</div>
      <div v-if="error" class="notice error small" role="alert">{{ error }}</div>
      <div v-if="deleting !== null" class="notice small" role="alertdialog" data-testid="delete-ties">
        <span>{{ deleting }}</span>
        <button type="button" class="btn btn-sm" @click="confirmDelete">Delete the entry</button>
        <button type="button" class="btn btn-sm" @click="deleting = null">Keep it</button>
      </div>

      <form v-if="labelling" class="checkpoint-bar" @submit.prevent="keepCheckpoint">
        <label for="checkpoint-label">Checkpoint label (optional)</label>
        <input id="checkpoint-label" ref="labelBox" v-model="label" type="text" maxlength="200" @keydown.esc="labelling = false" />
        <button class="btn btn-sm btn-primary" type="submit">Keep</button>
      </form>
      <form v-if="stashing" class="checkpoint-bar" @submit.prevent="keepThought">
        <label for="stash-thought">A thought for later (to the inbox, tied to this entry)</label>
        <input id="stash-thought" ref="stashBox" v-model="thought" type="text" maxlength="2000" @keydown.esc="(stashing = false), prose?.view.focus()" />
        <button class="btn btn-sm btn-primary" type="submit">Stash</button>
      </form>
      <form v-if="leaving" class="checkpoint-bar leave-bar" data-testid="leave-note" @submit.prevent="finishLeave(true)">
        <label for="leave-note">Before you go: what's next here?</label>
        <input id="leave-note" ref="leaveBox" v-model="leaveNote" type="text" maxlength="2000" placeholder="A note for next time" />
        <button class="btn btn-sm btn-primary" type="submit">Save and go</button>
        <button class="btn btn-sm" type="button" @click="finishLeave(false)">Skip</button>
      </form>
      <form v-if="asking" class="checkpoint-bar" data-testid="ask-bar" @submit.prevent="keepQuestion">
        <label for="ask-line">A question from “{{ asking.passage.slice(0, 60) }}”</label>
        <input id="ask-line" ref="askBox" v-model="askLine" type="text" maxlength="2000" placeholder="Your line (optional)" @keydown.esc="(asking = null), prose?.view.focus()" />
        <label class="toggle"><input v-model="askPark" type="checkbox" /> Park it</label>
        <button class="btn btn-sm btn-primary" type="submit">Save</button>
      </form>

      <div v-if="entry" class="title-wrap journal-head">
        <input v-model="title" class="chapter-title" aria-label="Entry title" maxlength="300" placeholder="Untitled" />
        <div class="journal-about">
          <label class="visually-hidden" for="entry-date">Date</label>
          <input id="entry-date" type="date" class="filter" :value="day" required @change="setAbout({ entry_date: ($event.target as HTMLInputElement).value })" />
          <label class="visually-hidden" for="entry-project">Project</label>
          <select id="entry-project" class="filter" :value="entry?.project ?? ''" @change="setAbout({ project: ($event.target as HTMLSelectElement).value || null })">
            <option value="">Whole world</option>
            <option v-for="p in world.projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
          </select>
          <span class="muted small visually-hidden">{{ projectName }}</span>
        </div>
      </div>
      <div ref="host" class="editor-host" :class="{ focus: focusMode }" :style="editorStyle" data-testid="editor" />
      <div v-if="pictureStatus" class="foot-status small" :class="{ 'error-text': pictureStatus.error }" role="status" data-testid="picture-status" @click="pictureStatus = null">{{ pictureStatus.text }}</div>
      <PicturePicker v-if="pickingPicture && world" :world="world.slug" upload title="Picture" :named="[...new Set((entry?.mentions ?? []).map((m) => m.entity_id))]" @pick="pickedPicture" @files="uploadPictures" @close="pickingPicture = false" />
    </div>

    <CompanionPanel
      v-if="entry && !showHistory && showPanel && !focusMode"
      :findings="findings"
      :checks="[]"
      :items="items"
      :note="nextNote"
      :back-in="backIn"
      :drafting="mode === 'drafting'"
      :stale="stale"
      :types="cards.types"
      :world="world.slug"
      :actions="panelActions"
      journal
      @dismiss-back="backIn = null"
      @tab="onTab"
    >
      <JournalSide
        :world="world.slug"
        :entry="entry"
        :read-only="false"
        :timeline="cards.timeline"
        :unit="unit"
        :times="cards.timed || cards.anyTime"
        :asof="asOf.asof ?? ''"
        :at="asOf.at ?? null"
        :era-of="cards.eraOf"
        :note="nextNote"
        :since="since"
        @note="saveNote"
        @checkpoint="checkpoint"
        @history="showHistory = true"
        @asof="setAsOf"
        @remove="askDelete"
      />
    </CompanionPanel>
    <UndoToast :label="toast?.label ?? null" :undo="toast?.undo ?? null" :actions="toast?.actions ?? []" :ms="toast?.actions ? 12000 : 6000" @dismiss="toast = null" />

    <HistoryPanel
      v-if="showHistory && entry"
      :world="world.slug"
      :chapter-id="entry.id"
      doc="journal"
      :current="prose?.view.state.doc.toString() ?? entry.body"
      @restore="restore"
      @close="showHistory = false"
    />
  </div>
</template>
