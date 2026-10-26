<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get } from "../api";
import {
  deleteEntity,
  EntityConflict,
  factSuggestions,
  fixes,
  getEntity,
  linkItem,
  relationTypes,
  sourceLink,
  updateEntity,
  type EntityChanges,
  type KindSuggestions,
} from "../bible";
import { resolutions, resolve, type Resolution } from "../companion";
import DecisionFollowups from "../components/DecisionFollowups.vue";
import EntityGallery from "../components/EntityGallery.vue";
import PictureText from "../components/PictureText.vue";
import FactsPanel from "../components/FactsPanel.vue";
import InlineText from "../components/InlineText.vue";
import MentionStrip from "../components/MentionStrip.vue";
import AsOfPicker from "../components/AsOfPicker.vue";
import RelationsPanel from "../components/RelationsPanel.vue";
import TimeField from "../components/TimeField.vue";
import { chronology as getChronology, type Chronology } from "../history";
import { ageText, birthOf, deathOf, ERA_COLOURS } from "../world/eras";
import { entitySlice } from "../world/slice";
import { timeText } from "../world/when";
import UndoToast from "../components/UndoToast.vue";
import { journalDay } from "../journal";
import { readLastUsed } from "../lastUsed";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, GENDERS, type EntityDetail, type EntityKind, type Gender, type RelationType, type SourceRef } from "../types";
import { evidenceRetired, reAnchor, type EvidenceFinding } from "../manuscript";
import { useCards } from "../world/cards";
import { Family, familyLinks, kinOf, kinText, readType } from "../world/family";
import type { GraphData } from "../world/graph";
import { isPronunciation, missingKey, missingLabels } from "../world/labels";
import { speciesText } from "../world/species";
import type { At } from "../world/time";
import { unitOf } from "../world/when";
import { imageFiles, NEEDS_NETWORK, pictureUrl, uploadPicture } from "../pictures";
import { useViewer } from "../stores/viewer";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const id = computed(() => String(route.params.id));
const detail = ref<EntityDetail | null>(null);
const types = ref<RelationType[]>([]);
const suggestions = ref<Record<string, KindSuggestions>>({});
const missing = ref(false);

// "as of chapter …" or "as of a time": what is true at that point on the clock (kept in the address, so it survives a
// reload: ?asof=<chapter> or ?at=<number>, docs/SPEC.md §13.1.6)
const asOfId = computed(() => (typeof route.query.asof === "string" ? route.query.asof : ""));
const atTime = computed(() => {
  const n = typeof route.query.at === "string" ? Number(route.query.at) : NaN;
  return Number.isFinite(n) ? n : null;
});
const asOf = computed<At | null>(() => (atTime.value !== null ? { time: atTime.value } : (cards.pointOf(asOfId.value || null) ?? null)));
const asOfOutside = computed(() => asOf.value !== null && typeof asOf.value === "object" && "outside" in asOf.value);
const unit = computed(() => unitOf(world.value));
function setAsOf(choice: { asof?: string; at?: number }) {
  void router.replace({ query: { ...route.query, asof: choice.asof, at: choice.at !== undefined ? String(choice.at) : undefined } });
}
const error = ref("");
const notice = ref("");

const SOURCE_LABEL: Record<string, string> = {
  item: "Item",
  decision: "Decision",
  journal: "Journal",
  entity: "Bible",
  chapter: "Chapter",
};
const projectName = (slug: string | null) =>
  slug ? (world.value?.projects.find((p) => p.slug === slug)?.name ?? slug) : "Whole world";
const kindLabel = (k: string) => ENTITY_KINDS.find((x) => x.value === k)?.label ?? k;

async function load() {
  error.value = "";
  missing.value = false;
  try {
    detail.value = await getEntity(worldSlug.value, id.value);
  } catch (e) {
    if ((e as { status?: number }).status === 404) missing.value = true;
    else error.value = (e as Error).message;
  }
}
watch([worldSlug, id], load, { immediate: true });
// the timeline may have changed (chapters added or moved) since the cards were loaded
watch(worldSlug, (w) => void cards.load(w, true), { immediate: true });
watch(
  worldSlug,
  async (w) => {
    [types.value, suggestions.value] = await Promise.all([relationTypes(w), factSuggestions(w)]).catch(() => [[], {}] as [RelationType[], Record<string, KindSuggestions>]);
  },
  { immediate: true },
);
const refreshSuggestions = async () => {
  suggestions.value = await factSuggestions(worldSlug.value).catch(() => suggestions.value);
};

/** After any change: this page, and the cards the editor colours names from. */
async function changed() {
  await load();
  void cards.refresh(worldSlug.value);
  void session.refreshNearMisses(worldSlug.value);
  void refreshSuggestions();
  void loadFamily();
}

// ---- an entry of more than one kind (docs/SPEC.md §14.8) ----
function addKind(k: EntityKind) {
  const e = detail.value?.entity;
  if (!e || !k) return;
  void save({ also_kinds: [...(e.also_kinds ?? []), k] });
}
/** the added kind becomes the main one, and the main one the first added */
function makeMain(k: EntityKind) {
  const e = detail.value?.entity;
  if (!e) return;
  void save({ kind: k, also_kinds: [e.kind, ...(e.also_kinds ?? []).filter((x) => x !== k)] });
}
const dropping = ref<{ kind: EntityKind; message: string } | null>(null);
/** removing an added kind says what uses it first; those relationships stay */
function dropKind(k: EntityKind) {
  const d = detail.value;
  if (!d) return;
  const byId = new Map(types.value.map((t) => [t.id, t]));
  const uses = d.relationships.filter((r) => {
    const t = byId.get(r.type_id);
    if (!t) return false;
    const side = r.a.id === d.entity.id ? t.a_kind : t.b_kind;
    return side === k;
  }).length;
  const word = kindLabel(k).toLowerCase();
  dropping.value = {
    kind: k,
    message: uses ? `${uses} relationship${uses === 1 ? " uses" : "s use"} ${d.entity.name} as a ${word}. They stay.` : `Nothing uses ${d.entity.name} as a ${word}.`,
  };
}
function confirmDrop() {
  const e = detail.value?.entity;
  const k = dropping.value?.kind;
  dropping.value = null;
  if (!e || !k) return;
  void save({ also_kinds: (e.also_kinds ?? []).filter((x) => x !== k) });
}

async function save(changes: EntityChanges) {
  const e = detail.value?.entity;
  if (!e) return;
  error.value = "";
  try {
    const out = await updateEntity(worldSlug.value, e, changes);
    await changed();
    if (out.kept_alias) keptName(out.kept_alias, out.name);
  } catch (err) {
    if (err instanceof EntityConflict) await load();
    error.value = (err as Error).message;
  }
}

// a rename keeps the old name as another name (docs/SPEC.md §11.1): say so, with a way to take it out again, or
// to replace it in the text
const toast = ref<{ label: string; actions: { label: string; run: () => unknown }[] } | null>(null);
function keptName(old: string, now: string) {
  const w = world.value;
  const project = w ? (w.projects.find((p) => p.slug === readLastUsed().project) ?? [...w.projects].sort((a, b) => a.position - b.position)[0]) : undefined;
  toast.value = {
    label: `Kept “${old}” as another name`,
    actions: [
      {
        label: "Remove",
        run: async () => {
          const e = detail.value?.entity;
          if (!e) return;
          await updateEntity(worldSlug.value, e, { aliases: e.aliases.filter((a) => a !== old) });
          notice.value = `“${old}” is no longer one of ${now}'s names.`;
          await changed();
        },
      },
      ...(project
        ? [{
            label: "Replace in the text…",
            run: () =>
              router.push({
                name: "replace",
                params: { world: worldSlug.value, project: project.slug },
                query: { find: old, replace: now, scope: (w?.projects.length ?? 0) > 1 ? "world" : undefined },
              }),
          }]
        : []),
    ],
  };
}

// other names and "not in this sense" phrases: chips with an add field
const newAlias = ref("");
const newExclusion = ref("");
function addTo(field: "aliases" | "exclusions") {
  const input = field === "aliases" ? newAlias : newExclusion;
  const e = detail.value?.entity;
  const v = input.value.trim();
  input.value = "";
  if (e && v && !e[field].includes(v)) void save({ [field]: [...e[field], v] });
}
function removeFrom(field: "aliases" | "exclusions", v: string) {
  const e = detail.value?.entity;
  if (e) void save({ [field]: e[field].filter((x) => x !== v) });
}

const editingNotes = ref(false);
const notes = ref("");

// ---- pictures (docs/SPEC.md §17.2): the main picture at the top, the gallery after the notes ----
const viewer = useViewer();
const main = computed(() => detail.value?.pictures?.[0] ?? null);
function openMain() {
  const list = detail.value?.pictures ?? [];
  viewer.show(list.map((g) => ({ id: g.id, caption: g.caption, name: g.name })), 0);
}
function galleryChanged(gallery: NonNullable<EntityDetail["pictures"]>) {
  if (detail.value) detail.value = { ...detail.value, pictures: gallery };
}
// pasting a picture into the notes while they are edited puts a picture line at the cursor
const notesBox = ref<HTMLTextAreaElement | null>(null);
async function pasteIntoNotes(e: ClipboardEvent) {
  const files = imageFiles(e.clipboardData);
  if (!files.length) return;
  e.preventDefault();
  if (navigator.onLine === false) {
    error.value = NEEDS_NETWORK;
    return;
  }
  for (const file of files) {
    try {
      notice.value = `Uploading ${file.name || "a picture"}…`;
      const p = await uploadPicture(worldSlug.value, file);
      cards.putPicture(p);
      const box = notesBox.value;
      const at = box ? box.selectionStart : notes.value.length;
      const before = notes.value.slice(0, at);
      const line = `${before && !before.endsWith("\n") ? "\n" : ""}![](picture:${p.id})\n`;
      notes.value = before + line + notes.value.slice(at);
      notice.value = "";
    } catch (err) {
      notice.value = "";
      error.value = (err as Error).message;
    }
  }
}

async function remove() {
  const e = detail.value?.entity;
  const f = detail.value?.follows;
  const follow = f && (f.facts || f.relationships)
    ? ` ${[f.facts ? `${f.facts} of its ${f.facts === 1 ? "facts follows a decision" : "facts follow decisions"}` : "", f.relationships ? `${f.relationships} of its ${f.relationships === 1 ? "relationships follows a decision" : "relationships follow decisions"}` : ""].filter(Boolean).join(" and ")}; they will be listed there as dropped.`
    : "";
  if (!e || !confirm(`Remove "${e.name}" from the bible? Its facts, relationships and tags go too; the texts stay as they are.${follow}`)) return;
  await deleteEntity(worldSlug.value, e.id);
  void cards.refresh(worldSlug.value);
  await router.push({ name: "bible-kind", params: { world: worldSlug.value, kind: e.kind } });
}

async function act(fn: () => Promise<unknown>, done: string) {
  error.value = "";
  try {
    await fn();
    notice.value = done;
    await changed();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

const groups = computed(() => {
  const out = new Map<string, NonNullable<typeof detail.value>["mentions"]>();
  for (const m of detail.value?.mentions ?? []) {
    const key = projectName(m.project);
    out.set(key, [...(out.get(key) ?? []), m]);
  }
  return [...out.entries()];
});

// the three fixes, as plain functions for the template
const fixReplace = fixes.replace;
const fixSpelling = (w: string, token: string, entityId: string) => fixes.addSpelling(w, token, entityId);
const fixIgnore = fixes.notATypo;

const tag = (m: SourceRef) => act(() => linkItem(worldSlug.value, m.source_id, id.value), "Tagged.");

// ---- phase 11: more views of the bible (docs/SPEC.md §12) ----

// the level (world or one project) is shown only in a world with more than one project
const levels = computed(() => (world.value && world.value.projects.length > 1 ? world.value.projects : []));
// said after the name, in small type
const pronunciation = computed(() => detail.value?.facts.find((f) => isPronunciation(f.label) && f.value.trim())?.value ?? "");
// what a character is, as of the page's chapter (else at the end of the story): "selkie · appears as human"
const species = computed(() => {
  const e = detail.value?.entity;
  if (e?.kind !== "character") return "";
  const at = atTime.value !== null ? { time: atTime.value } : asOfId.value || cards.endChapter;
  return speciesText(cards.asOf(cards.byId.get(e.id), at));
});

// the mentions strip: how often each chapter names the entry
const chapterCounts = computed(() => new Map((detail.value?.mentions ?? []).filter((m) => m.source_table === "chapter").map((m) => [m.source_id, m.count])));
// uses of a name it shares that nothing settles: faint cells, counted for none (docs/SPEC.md §14.10)
const unsettledCounts = computed(() => new Map((detail.value?.unsettled ?? []).filter((u) => u.source_table === "chapter").map((u) => [u.source_id, u.count])));

// the family: recorded parents, children and marriages make a tree; kin worked out from them, dimmed, as of the page's
// chapter (docs/SPEC.md §12.2)
const graph = ref<GraphData | null>(null);
async function loadFamily() {
  if (detail.value?.entity.kind !== "character") return;
  try {
    graph.value = await get<GraphData>(`/api/worlds/${encodeURIComponent(worldSlug.value)}/graph`);
  } catch {
    graph.value = null;
  }
}
watch(() => detail.value?.entity.id, () => void loadFamily());
const hasFamily = computed(() => detail.value?.entity.kind === "character" && detail.value.relationships.some((r) => r.a.kind === "character" && r.b.kind === "character" && readType(r.label, r.reverse_label)?.kind !== "sibling" && !!readType(r.label, r.reverse_label)));
const kin = computed(() => {
  const g = graph.value;
  const e = detail.value?.entity;
  if (!g || !e || e.kind !== "character") return [];
  const fam = new Family(familyLinks(g, { asOf: asOf.value, indexOf: cards.indexOf, standings: new Set(["canon", "planned", "rumour"]) }));
  const node = new Map(g.nodes.map((n) => [n.id, n]));
  return kinOf(fam, e.id)
    .filter((k) => !k.recorded)
    .map((k) => ({ ...k, who: node.get(k.id)!, word: kinText(k, node.get(k.id)?.gender), path: k.via.map((x) => node.get(x)?.name ?? "?") }))
    .sort((a, b) => a.who.name.localeCompare(b.who.name));
});

// evidence resting on a passage in a retired chapter (docs/SPEC.md §13.6.3): the Archivist's, on the entry's page
const evidence = ref<EvidenceFinding[]>([]);
async function loadEvidence() {
  evidence.value = await evidenceRetired(worldSlug.value).catch(() => []);
}
watch([worldSlug, id], () => void loadEvidence(), { immediate: true });
const evidenceHere = computed(() => evidence.value.filter((x) => x.entities.some((e) => e.id === id.value)));
const anchoring = ref<string | null>(null);
const anchorTo = ref("");
async function doAnchor(x: EvidenceFinding) {
  if (!anchorTo.value) return;
  await act(() => reAnchor(worldSlug.value, x.kind, x.id, anchorTo.value), "The evidence points there now.");
  anchoring.value = null;
  await loadEvidence();
}
async function dismissEvidence(x: EvidenceFinding) {
  await act(() => resolve(worldSlug.value, "evidence_retired", x.key, "intentional"), "Dismissed.");
  await loadEvidence();
}

// ---- history (docs/SPEC.md §13.2): an event's when, an era's colour, its tellings; ages; the entry's own timeline ----
const isEvent = computed(() => detail.value?.entity.kind === "event");
const when = computed(() => detail.value?.entity.when ?? null);
const whenMode = computed(() => (!when.value ? "none" : when.value.outside ? "outside" : when.value.chapter ? "chapter" : "time"));
const whenEra = computed(() => cards.eraOf(cards.byId.get(id.value)?.when?.at ?? (when.value?.chapter ? cards.timeline.find((c) => c.id === when.value!.chapter)?.set_time : null)));
function setWhen(mode: string) {
  if (mode === "none") void save({ time_chapter_id: null, time_at: null, outside_time: false });
  else if (mode === "outside") void save({ outside_time: true });
  else if (mode === "chapter") picking.value = "chapter";
  else picking.value = "time";
}
const picking = ref<"chapter" | "time" | null>(null);
const isEra = computed(() => cards.eras.some((e) => e.id === id.value));
const eraColour = computed(() => cards.eras.find((e) => e.id === id.value)?.colour ?? null);
// ages, beside the facts: "34 as of chapter 9 · born year 278"
const chaptersMap = computed(() => new Map(cards.timeline.map((c) => [c.id, c])));
const life = computed(() => {
  const c = cards.byId.get(id.value);
  if (!c || c.kind !== "character") return null;
  const birth = birthOf(c, cards.byId, chaptersMap.value);
  const death = deathOf(c, cards.byId, chaptersMap.value);
  if (!birth && !death) return null;
  const point = asOf.value === null ? null : typeof asOf.value === "number" ? cards.indexOf.timeOf?.(asOf.value) ?? null : "time" in asOf.value ? asOf.value.time : null;
  const where = atTime.value !== null ? `as of ${timeText({ time_at: atTime.value }, unit.value)}` : asOfId.value ? `as of ${cards.chapterTitle(asOfId.value) ?? "this chapter"}` : "";
  const age = point != null ? ageText(birth, death, { t: point, approx: false }, { word: false }) : "";
  const parts = [age && where ? `${age} ${where}` : "", birth ? `born ${timeText({ time_at: birth.t, time_approx: birth.approx }, unit.value)}` : "", death && birth ? `died at ${Math.floor(death.t - birth.t)}` : death ? `died ${timeText({ time_at: death.t, time_approx: death.approx }, unit.value)}` : ""];
  return parts.filter(Boolean).join(" · ");
});
// the entry's own slice of the Timeline
const chron = ref<Chronology | null>(null);
watch(worldSlug, async (w) => (chron.value = await getChronology(w).catch(() => null)), { immediate: true });
const slice = computed(() => {
  const c = cards.byId.get(id.value);
  if (!c) return [];
  return entitySlice({ card: c, cards: cards.byId, timeline: cards.timeline, chronology: chron.value, eras: cards.eras, unit: unit.value });
});
const sliceAfter = computed(() => {
  const p = asOf.value === null ? null : typeof asOf.value === "number" ? cards.indexOf.timeOf?.(asOf.value) ?? null : "time" in asOf.value ? asOf.value.time : null;
  return (t: number | null) => p != null && t != null && t > p;
});

// labels expected on every entry of this kind that it hasn't got: the Archivist's findings, on its own page
const resolved = ref<Resolution[]>([]);
watch(worldSlug, async (w) => (resolved.value = await resolutions(w).catch(() => [])), { immediate: true });
const missingHere = computed(() => {
  const e = detail.value?.entity;
  const c = e ? cards.byId.get(e.id) : undefined;
  if (!e || !c) return [];
  const done = new Set(resolved.value.filter((r) => r.rule === "missing_label").map((r) => r.key));
  return missingLabels({ ...c, labels: detail.value!.facts.map((f) => f.label.trim().toLowerCase()) }, cards.expected(e.kind)).filter((l) => !done.has(missingKey(e.id, l)));
});
const plural = (k: string) => ENTITY_KINDS.find((x) => x.value === k)?.plural.toLowerCase() ?? k;
function addIt(label: string) {
  void router.replace({ query: { ...route.query, add: label } });
}
async function notForThisOne(label: string) {
  const e = detail.value?.entity;
  if (!e) return;
  try {
    await resolve(worldSlug.value, "missing_label", missingKey(e.id, label), "intentional");
    resolved.value = await resolutions(worldSlug.value);
  } catch (err) {
    error.value = (err as Error).message;
  }
}
</script>

<template>
  <NotFoundView v-if="!world || missing" what="entry" />
  <template v-else-if="detail">
    <div class="page-head entry-head" :class="`k-${detail.entity.kind}`">
      <div class="grow">
        <div class="crumbs" data-testid="entry-kinds">
          <RouterLink :to="{ name: 'bible-kind', params: { world: world.slug, kind: detail.entity.kind } }">
            {{ ENTITY_KINDS.find((k) => k.value === detail!.entity.kind)?.plural }}
          </RouterLink>
          <!-- its kinds, in order: "Place · also a character" (docs/SPEC.md §14.8) -->
          <template v-for="k in detail.entity.also_kinds ?? []" :key="k">
            · also a <RouterLink :to="{ name: 'bible-kind', params: { world: world.slug, kind: k } }" :class="`k-${k}`">{{ kindLabel(k).toLowerCase() }}</RouterLink>
            <button type="button" class="linkish small" :data-testid="`make-main-${k}`" @click="makeMain(k)">Make main</button>
            <button type="button" class="chip-x" :aria-label="`No longer a ${kindLabel(k).toLowerCase()}`" @click="dropKind(k)">×</button>
          </template>
        </div>
        <h1 class="kname"><InlineText :value="detail.entity.name" label="Name" :maxlength="200" @save="(v) => v && save({ name: v })" /><span v-if="pronunciation" class="pronunciation" data-testid="pronunciation">{{ pronunciation }}</span><span v-if="species" class="species-words" data-testid="species-words">{{ species }}</span></h1>
        <p class="entry-summary">
          <InlineText :value="detail.entity.summary" label="One line" placeholder="Add a one-line summary, shown when hovering the name" @save="(v) => save({ summary: v })" />
        </p>
        <div class="chips aliases" data-testid="aliases">
          <span class="muted small">Also:</span>
          <span v-for="a in detail.entity.aliases" :key="a" class="chip static">
            {{ a }}<button type="button" class="chip-x" :aria-label="`Remove ${a}`" @click="removeFrom('aliases', a)">×</button>
          </span>
          <input v-model="newAlias" class="chip-input" placeholder="+ other name" aria-label="Add another name" maxlength="200" @keydown.enter.prevent="addTo('aliases')" @blur="addTo('aliases')" />
        </div>
      </div>
      <figure v-if="main" class="main-picture" data-testid="main-picture" :data-picture="main.id">
        <button type="button" class="picture-box opens" :style="{ aspectRatio: `${main.width} / ${main.height}` }" :aria-label="`Open ${main.caption || main.name}`" @click="openMain">
          <img :src="pictureUrl(main.id, 'view')" :alt="main.caption || main.name" />
        </button>
        <figcaption v-if="main.caption" data-testid="main-caption">{{ main.caption }}</figcaption>
      </figure>
      <div class="actions">
        <RouterLink class="btn btn-sm" :to="{ name: 'entity-read', params: { world: world.slug, id: detail.entity.id } }" data-testid="read-thread">
          Read where {{ detail.entity.name }} appears
        </RouterLink>
        <RouterLink class="btn btn-sm" :to="{ name: 'entity-read', params: { world: world.slug, id: detail.entity.id }, query: { in: 'planning' } }" data-testid="read-planning-link">… in the planning</RouterLink>
        <RouterLink v-if="detail.entity.kind === 'place'" class="btn btn-sm" :to="{ name: 'chart', params: { world: world.slug }, query: { focus: detail.entity.id, ...(asOfId ? { asof: asOfId } : {}) } }" data-testid="on-the-chart">On the chart</RouterLink>
        <RouterLink v-if="hasFamily" class="btn btn-sm" :to="{ name: 'graph', params: { world: world.slug }, query: { view: 'family', centre: detail.entity.id, ...(asOfId ? { asof: asOfId } : {}) } }" data-testid="family-tree-link">Family tree</RouterLink>
        <select class="filter" :value="detail.entity.kind" aria-label="Kind" @change="save({ kind: ($event.target as HTMLSelectElement).value as EntityKind })">
          <option v-for="k in ENTITY_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
        <select class="filter" value="" aria-label="Also a…" data-testid="also-a" title="It is this kind as well, and stays one entry" @change="addKind(($event.target as HTMLSelectElement).value as EntityKind), (($event.target as HTMLSelectElement).value = '')">
          <option value="">Also a…</option>
          <option v-for="k in ENTITY_KINDS.filter((x) => x.value !== detail!.entity.kind && !(detail!.entity.also_kinds ?? []).includes(x.value))" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
        <label v-if="detail.entity.kind === 'character'" class="small muted gender-pick">Gender
          <select class="filter" :value="detail.entity.gender ?? ''" aria-label="Gender" data-testid="gender" @change="save({ gender: (($event.target as HTMLSelectElement).value || null) as Gender | null })">
            <option v-for="g in GENDERS" :key="g.label" :value="g.value ?? ''">{{ g.label }}</option>
          </select>
        </label>
        <select v-if="levels.length" class="filter" :value="detail.entity.project ?? ''" aria-label="Level" data-testid="level" title="Whose part of the bible it is in" @change="save({ project: ($event.target as HTMLSelectElement).value || null })">
          <option value="">World</option>
          <option v-for="p in levels" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
        <button type="button" class="btn btn-sm" @click="remove">Remove</button>
      </div>
    </div>

    <div v-if="dropping" class="notice small" role="alertdialog" data-testid="drop-kind">
      <span>{{ dropping.message }}</span>
      <button type="button" class="btn btn-sm" @click="confirmDrop">Remove the kind</button>
      <button type="button" class="btn btn-sm" @click="dropping = null">Keep it</button>
    </div>
    <div v-if="notice" class="notice ok" role="status">{{ notice }}</div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <MentionStrip v-if="cards.timeline.length" :world="world.slug" :entity-id="detail.entity.id" :timeline="cards.timeline" :counts="chapterCounts" :unsettled="unsettledCounts" :as-of="asOf" :index-of="cards.indexOf" :class="`k-${detail.entity.kind}`" />

    <section v-if="missingHere.length || evidenceHere.length" class="card findings-card" data-testid="entity-findings">
      <div v-for="x in evidenceHere" :key="x.key" class="finding" data-rule="evidence_retired" data-testid="evidence-finding">
        <span class="small">{{ x.message }} <span class="muted">“{{ x.passage }}”</span></span>
        <form v-if="anchoring === x.key" class="actions" @submit.prevent="doAnchor(x)">
          <select v-model="anchorTo" class="filter" aria-label="Re-anchor to">
            <optgroup v-if="x.found.length" label="Where the passage is now">
              <option v-for="c in x.found" :key="c.id" :value="c.id">{{ c.title }}{{ c.state === "experiment" ? " (draft)" : "" }}</option>
            </optgroup>
            <optgroup label="The book">
              <option v-for="c in cards.timeline.filter((c) => !x.found.some((y) => y.id === c.id))" :key="c.id" :value="c.id">{{ c.title }}</option>
            </optgroup>
          </select>
          <button class="btn btn-sm btn-primary" type="submit">Re-anchor</button>
          <button class="btn btn-sm" type="button" @click="anchoring = null">Cancel</button>
        </form>
        <span v-else class="qrow">
          <button type="button" class="qchip primary" @click="(anchoring = x.key), (anchorTo = x.found[0]?.id ?? '')">Re-anchor…</button>
          <button type="button" class="qchip quiet" @click="dismissEvidence(x)">Dismiss</button>
        </span>
      </div>
      <div v-for="l in missingHere" :key="l" class="finding" data-rule="missing_label">
        <span class="small">{{ detail.entity.name }} has no {{ l }} (expected for {{ plural(detail.entity.kind) }}).</span>
        <span class="qrow">
          <button type="button" class="qchip primary" @click="addIt(l)">Add it</button>
          <button type="button" class="qchip quiet" @click="notForThisOne(l)">Not for this one</button>
        </span>
      </div>
    </section>

    <div v-if="cards.timeline.length || cards.anyTime" class="as-of">
      <AsOfPicker :timeline="cards.timeline" :unit="unit" :asof="asOfId" :at="atTime" :times="cards.timed || cards.anyTime" :era-of="cards.eraOf" @pick="setAsOf" />
      <span v-if="asOfOutside" class="muted small" data-testid="outside-note">Outside time: what changes over time isn't shown</span>
    </div>

    <details class="card matching">
      <summary>Matching in the text</summary>
      <label class="check"><input type="checkbox" :checked="!detail.entity.match_case" @change="save({ match_case: !($event.target as HTMLInputElement).checked })" /> Match whatever the capitals (for names that are never ordinary words)</label>
      <label v-if="detail.entity.kind === 'character'" class="check"><input type="checkbox" :checked="detail.entity.first_name_alias" @change="save({ first_name_alias: ($event.target as HTMLInputElement).checked })" /> Match the first name on its own, when nobody else uses it</label>
      <div class="chips">
        <span class="muted small">Not a name in:</span>
        <span v-for="x in detail.entity.exclusions" :key="x" class="chip static">
          {{ x }}<button type="button" class="chip-x" :aria-label="`Remove ${x}`" @click="removeFrom('exclusions', x)">×</button>
        </span>
        <input v-model="newExclusion" class="chip-input" placeholder="+ phrase, e.g. rose garden" aria-label="Add a phrase where it isn't a name" maxlength="200" @keydown.enter.prevent="addTo('exclusions')" />
      </div>
    </details>

    <p v-if="life" class="small life-line" data-testid="life-line">{{ life }}</p>

    <section v-if="isEvent" class="card event-when" data-testid="event-when">
      <div class="card-head"><h2>When</h2></div>
      <div class="actions">
        <select class="filter" :value="picking ?? whenMode" aria-label="When it happens" data-testid="when-mode" @change="setWhen(($event.target as HTMLSelectElement).value)">
          <option value="none">not placed yet</option>
          <option value="chapter">in a chapter</option>
          <option value="time">a time</option>
          <option value="outside">outside time</option>
        </select>
        <select v-if="(picking ?? whenMode) === 'chapter'" class="filter" :value="when?.chapter ?? ''" aria-label="The chapter it happens in" data-testid="when-chapter"
          @change="(picking = null), save({ time_chapter_id: ($event.target as HTMLSelectElement).value || null })">
          <option value="" disabled>a chapter…</option>
          <option v-for="c in cards.timeline" :key="c.id" :value="c.id">{{ c.title }}</option>
        </select>
        <TimeField v-if="(picking ?? whenMode) === 'time'" :value="{ time_at: when?.at ?? null, time_end: when?.end, time_label: when?.label, time_approx: when?.approx, outside_time: false }" :unit="unit" label="When it happens" :era-of="cards.eraOf"
          @save="(v) => ((picking = null), save({ time_chapter_id: null, time_at: v.time_at, time_end: v.time_end ?? null, time_label: v.time_label ?? null, time_approx: !!v.time_approx, outside_time: !!v.outside_time }))" />
        <span v-if="whenMode === 'chapter' && whenEra" class="small era-tint" :class="`era-${whenEra.colour}`" data-testid="when-era">{{ whenEra.name }}</span>
        <span v-if="whenMode === 'outside'" class="small muted">outside time</span>
      </div>
      <div v-if="isEra" class="era-colours" data-testid="era-colours">
        <span class="small muted">Colour</span>
        <button v-for="c in ERA_COLOURS" :key="c" type="button" class="era-swatch" :class="[`era-${c}`, { on: eraColour === c }]" :aria-label="`Colour ${c}`" :aria-pressed="eraColour === c" @click="save({ era_colour: c })" />
      </div>
      <div v-if="detail.tellings?.length" class="told-in" data-testid="told-in">
        <h3 class="small muted">Told in</h3>
        <blockquote v-for="t in detail.tellings" :key="t.id" class="telling" data-testid="telling">
          <p class="prose">“{{ t.passage }}”</p>
          <footer class="small">
            <RouterLink v-if="t.chapter" :to="{ name: 'chapter', params: { world: world.slug, id: t.chapter.id }, query: t.at >= 0 ? { at: String(t.at) } : {} }">{{ t.chapter.title }}</RouterLink>
            <span v-if="t.changed" class="pill warn" data-testid="passage-changed">passage changed</span>
          </footer>
        </blockquote>
      </div>
      <div v-if="detail.notes?.length" class="told-in" data-testid="noted-in">
        <h3 class="small muted">Noted in</h3>
        <blockquote v-for="n in detail.notes" :key="n.id" class="telling" data-testid="note">
          <p class="prose">“{{ n.passage }}”</p>
          <footer class="small">
            <RouterLink :to="{ name: 'journal-entry', params: { world: world.slug, id: n.journal.id }, query: n.changed ? {} : { passage: n.passage } }">the Journal, {{ journalDay(n.journal.date) }}<template v-if="n.journal.title"> · {{ n.journal.title }}</template></RouterLink>
            <span v-if="n.changed" class="pill warn">passage changed</span>
          </footer>
        </blockquote>
      </div>
    </section>

    <FactsPanel
      :world="world.slug"
      :entity="detail.entity"
      :facts="detail.facts"
      :suggestions="suggestions[detail.entity.kind] ?? { labels: [], common: [], values: {} }"
      :several="(label: string) => cards.several(detail!.entity.kind, label)"
      :chapter-titles="detail.chapter_titles"
      :journal-entries="detail.journal_entries"
      :timeline="cards.timeline"
      :as-of="asOf"
      :index-of="cards.indexOf"
      :unit="unit"
      :era-of="cards.eraOf"
      @changed="changed"
      @error="(m) => (error = m)"
    />

    <RelationsPanel
      :world="world.slug"
      :entity="detail.entity"
      :relationships="detail.relationships"
      :types="types"
      :names="cards.names"
      :journal-entries="detail.journal_entries"
      :timeline="cards.timeline"
      :as-of="asOf"
      :index-of="cards.indexOf"
      :unit="unit"
      :era-of="cards.eraOf"
      @changed="changed"
      @error="(m) => (error = m)"
    />

    <section v-if="kin.length" class="card family-worked-out" data-testid="family-worked-out">
      <div class="card-head">
        <h2>Family, worked out</h2>
        <span class="muted small">From the recorded parents, children and marriages{{ asOf !== null ? ", as of this point" : "" }}. To make one a relationship, record it above.</span>
      </div>
      <ul class="plain-list">
        <li v-for="k in kin" :key="k.id + k.relation" :class="`k-${k.who.kind}`">
          <span class="kin-word">{{ k.word }}</span> ·
          <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: k.id }, query: asOfId ? { asof: asOfId } : {} }">{{ k.who.name }}</RouterLink>
          <span v-if="k.path.length" class="muted small"> (via {{ k.path.join(" → ") }})</span>
        </li>
      </ul>
    </section>

    <section v-if="slice.length" class="card entity-timeline" data-testid="entity-timeline">
      <div class="card-head">
        <h2>Timeline</h2>
        <RouterLink class="small" :to="{ name: 'timeline', params: { world: world.slug }, query: { lanes: detail.entity.id } }" data-testid="open-in-timeline">Open in the Timeline</RouterLink>
      </div>
      <ol class="rows slice">
        <li v-for="r in slice" :key="r.key" :class="{ off: sliceAfter(r.t) }" data-testid="slice-row">
          <span class="slice-when small" :class="r.era ? `era-${r.era.colour} era-tint` : 'muted'">{{ r.when || "—" }}<template v-if="r.era"> · {{ r.era.name }}</template></span>
          <span class="grow">
            <RouterLink v-if="r.link?.entity" :to="{ name: 'entity', params: { world: world.slug, id: r.link.entity } }">{{ r.text }}</RouterLink>
            <RouterLink v-else-if="r.link?.chapter" :to="{ name: 'chapter', params: { world: world.slug, id: r.link.chapter } }">{{ r.text }}</RouterLink>
            <template v-else>{{ r.text }}</template>
          </span>
          <span v-if="r.age" class="small muted" data-testid="slice-age">{{ r.age }}</span>
        </li>
      </ol>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Notes</h2>
        <button v-if="!editingNotes" type="button" class="btn btn-sm" @click="(notes = detail!.entity.body), (editingNotes = true)">Edit</button>
      </div>
      <form v-if="editingNotes" class="form wide" @submit.prevent="(editingNotes = false), save({ body: notes })">
        <label for="e-body" class="visually-hidden">Notes</label>
        <textarea id="e-body" ref="notesBox" v-model="notes" class="capture-box" rows="10" @paste="pasteIntoNotes" />
        <div class="actions">
          <button class="btn btn-primary btn-sm" type="submit">Save</button>
          <button class="btn btn-sm" type="button" @click="editingNotes = false">Cancel</button>
        </div>
      </form>
      <div v-else-if="detail.entity.body" class="entry-notes" data-testid="entry-notes"><PictureText :text="detail.entity.body" :world="world.slug" /></div>
      <p v-else class="empty">No notes.</p>
    </section>

    <EntityGallery :world="world.slug" :entity-id="detail.entity.id" :entity-name="detail.entity.name" :pictures="detail.pictures ?? []" @changed="galleryChanged" />

    <section v-if="detail.decisions.length" class="card">
      <div class="card-head"><h2>Decisions</h2></div>
      <ul class="rows" data-testid="entity-decisions">
        <li v-for="d in detail.decisions" :key="d.id" class="fu-line">
          <span class="muted small">{{ d.decided_on }}</span>
          <span class="grow">{{ d.text }}</span>
          <span v-if="!d.tagged" class="muted small" title="Names it without being tagged">mentions</span>
          <DecisionFollowups :world="world.slug" :decision="d" @counts="(c) => (d.followups = c)" />
        </li>
      </ul>
    </section>

    <section v-if="detail.near_misses.length" class="card" data-testid="entity-near-misses">
      <div class="card-head"><h2>Possible misspellings</h2></div>
      <ul class="rows">
        <li v-for="m in detail.near_misses" :key="`${m.source_id}-${m.snippet.before.length}`">
          <div class="grow">
            <div class="snippet">{{ m.snippet.before }}<mark class="near-miss static">{{ m.snippet.match }}</mark>{{ m.snippet.after }}</div>
            <RouterLink class="small" :to="sourceLink(world.slug, m.source_table, m.source_id)">{{ SOURCE_LABEL[m.source_table] }}: {{ m.title }}</RouterLink>
          </div>
          <div class="actions">
            <button type="button" class="btn btn-sm" @click="act(() => fixReplace(world!.slug, m.token, detail!.entity.id, { table: m.source_table, id: m.source_id }), 'Replaced.')">Replace</button>
            <button type="button" class="btn btn-sm" @click="act(() => fixSpelling(world!.slug, m.token, detail!.entity.id), 'Spelling added.')">Another spelling</button>
            <button type="button" class="btn btn-sm" @click="act(() => fixIgnore(world!.slug, m.token), 'Marked as not a typo.')">Not a typo</button>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="detail.unlinked.length" class="card">
      <div class="card-head">
        <h2>Mentioned but not tagged</h2>
        <span class="muted small">Items that name {{ detail.entity.name }} without being tagged with it.</span>
      </div>
      <ul class="rows" data-testid="unlinked">
        <li v-for="m in detail.unlinked" :key="m.source_id">
          <RouterLink class="grow" :to="sourceLink(world.slug, 'item', m.source_id)">{{ m.title }}</RouterLink>
          <button type="button" class="btn btn-sm" @click="tag(m)">Tag</button>
        </li>
      </ul>
    </section>

    <section v-if="detail.first_appearance.length" class="card">
      <div class="card-head"><h2>First appears</h2></div>
      <ul class="rows" data-testid="first-appearance">
        <li v-for="f in detail.first_appearance" :key="f.project">
          <span class="grow">
            <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: f.chapter_id } }">{{ f.title }}</RouterLink>
            <span class="muted small"> · chapter {{ f.position + 1 }}</span>
          </span>
          <span class="pill">{{ projectName(f.project) }}</span>
        </li>
      </ul>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Mentions</h2>
        <span class="muted small">{{ detail.entity.mention_count }} in {{ detail.mentions.length }} texts</span>
      </div>
      <template v-for="[project, list] in groups" :key="project">
        <h3 class="small muted group-title">{{ project }}</h3>
        <ul class="rows" data-testid="mentions">
          <li v-for="m in list" :key="`${m.source_table}-${m.source_id}`">
            <div class="grow">
              <template v-if="m.source_table === 'journal' || m.source_table === 'entity' || m.source_table === 'chapter'">
                <RouterLink :to="sourceLink(world.slug, m.source_table, m.source_id)">{{ m.title }}</RouterLink>
                <div class="snippet muted">{{ m.snippet.before }}<mark>{{ m.snippet.match }}</mark>{{ m.snippet.after }}</div>
              </template>
              <RouterLink v-else class="snippet snippet-link" :to="sourceLink(world.slug, m.source_table, m.source_id)"
                >{{ m.snippet.before }}<mark>{{ m.snippet.match }}</mark>{{ m.snippet.after }}</RouterLink
              >
            </div>
            <span class="pill">{{ SOURCE_LABEL[m.source_table] }}</span>
            <span v-if="m.count > 1" class="muted small">×{{ m.count }}</span>
          </li>
        </ul>
      </template>
      <p v-if="!detail.mentions.length" class="empty">Not mentioned anywhere yet.</p>
      <div v-if="detail.unsettled?.length" class="unsettled" data-testid="unsettled">
        <h3 class="small muted group-title">Not settled</h3>
        <p class="small muted">A name it shares with another entry, with no choice line saying which one is meant. Counted for neither.</p>
        <ul class="rows">
          <li v-for="u in detail.unsettled" :key="`${u.source_table}-${u.source_id}`" class="faint-row">
            <div class="grow">
              <RouterLink :to="sourceLink(world.slug, u.source_table, u.source_id)">{{ u.title }}</RouterLink>
              <span class="muted small"> · “{{ u.matched }}”</span>
            </div>
            <span class="pill">{{ SOURCE_LABEL[u.source_table] }}</span>
            <span class="muted small">×{{ u.count }}</span>
          </li>
        </ul>
      </div>
    </section>

    <section v-if="detail.linked_items.length" class="card">
      <div class="card-head"><h2>Tagged items</h2></div>
      <ul class="rows">
        <li v-for="i in detail.linked_items" :key="i.id">
          <RouterLink class="grow" :to="sourceLink(world.slug, 'item', i.id)">{{ i.title }}</RouterLink>
          <span class="pill">{{ i.status }}</span>
        </li>
      </ul>
    </section>
    <span class="visually-hidden">{{ kindLabel(detail.entity.kind) }}</span>
    <UndoToast :label="toast?.label ?? null" :undo="null" :actions="toast?.actions ?? []" :ms="12000" @dismiss="toast = null" />
  </template>
</template>
