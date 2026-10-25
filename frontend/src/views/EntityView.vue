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
import FactsPanel from "../components/FactsPanel.vue";
import InlineText from "../components/InlineText.vue";
import MentionStrip from "../components/MentionStrip.vue";
import RelationsPanel from "../components/RelationsPanel.vue";
import UndoToast from "../components/UndoToast.vue";
import { readLastUsed } from "../lastUsed";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, GENDERS, type EntityDetail, type EntityKind, type Gender, type RelationType, type SourceRef } from "../types";
import { useCards } from "../world/cards";
import { Family, familyLinks, kinOf, kinText, readType } from "../world/family";
import type { GraphData } from "../world/graph";
import { isPronunciation, missingKey, missingLabels } from "../world/labels";
import { speciesText } from "../world/species";
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

// "as of chapter …": what is true at that point in the story (kept in the address, so it survives a reload)
const asOfId = computed(() => (typeof route.query.asof === "string" ? route.query.asof : ""));
const asOf = computed(() => cards.indexOf(asOfId.value || null) ?? null);
const asOfProjects = computed(() => {
  const out: { name: string; chapters: typeof cards.timeline }[] = [];
  for (const c of cards.timeline) {
    const last = out[out.length - 1];
    if (last?.name === c.project_name) last.chapters.push(c);
    else out.push({ name: c.project_name, chapters: [c] });
  }
  return out;
});
function setAsOf(id: string) {
  void router.replace({ query: { ...route.query, asof: id || undefined } });
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

async function remove() {
  const e = detail.value?.entity;
  if (!e || !confirm(`Remove "${e.name}" from the bible? Its facts, relationships and tags go too; the texts stay as they are.`)) return;
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
  const at = asOfId.value || cards.timeline[cards.timeline.length - 1]?.id || null;
  return speciesText(cards.asOf(cards.byId.get(e.id), at));
});

// the mentions strip: how often each chapter names the entry
const chapterCounts = computed(() => new Map((detail.value?.mentions ?? []).filter((m) => m.source_table === "chapter").map((m) => [m.source_id, m.count])));

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
        <div class="crumbs">
          <RouterLink :to="{ name: 'bible-kind', params: { world: world.slug, kind: detail.entity.kind } }">
            {{ ENTITY_KINDS.find((k) => k.value === detail!.entity.kind)?.plural }}
          </RouterLink>
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
      <div class="actions">
        <RouterLink class="btn btn-sm" :to="{ name: 'entity-read', params: { world: world.slug, id: detail.entity.id } }" data-testid="read-thread">
          Read where {{ detail.entity.name }} appears
        </RouterLink>
        <RouterLink v-if="hasFamily" class="btn btn-sm" :to="{ name: 'graph', params: { world: world.slug }, query: { view: 'family', centre: detail.entity.id, ...(asOfId ? { asof: asOfId } : {}) } }" data-testid="family-tree-link">Family tree</RouterLink>
        <select class="filter" :value="detail.entity.kind" aria-label="Kind" @change="save({ kind: ($event.target as HTMLSelectElement).value as EntityKind })">
          <option v-for="k in ENTITY_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
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

    <div v-if="notice" class="notice ok" role="status">{{ notice }}</div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <MentionStrip v-if="cards.timeline.length" :world="world.slug" :entity-id="detail.entity.id" :timeline="cards.timeline" :counts="chapterCounts" :as-of="asOf" :class="`k-${detail.entity.kind}`" />

    <section v-if="missingHere.length" class="card findings-card" data-testid="entity-findings">
      <div v-for="l in missingHere" :key="l" class="finding" data-rule="missing_label">
        <span class="small">{{ detail.entity.name }} has no {{ l }} (expected for {{ plural(detail.entity.kind) }}).</span>
        <span class="qrow">
          <button type="button" class="qchip primary" @click="addIt(l)">Add it</button>
          <button type="button" class="qchip quiet" @click="notForThisOne(l)">Not for this one</button>
        </span>
      </div>
    </section>

    <div v-if="cards.timeline.length" class="as-of">
      <label for="as-of" class="small muted">As of</label>
      <select id="as-of" class="filter" :value="asOfId" data-testid="as-of" @change="setAsOf(($event.target as HTMLSelectElement).value)">
        <option value="">the whole story</option>
        <optgroup v-for="p in asOfProjects" :key="p.name" :label="p.name">
          <option v-for="c in p.chapters" :key="c.id" :value="c.id">{{ c.title }}</option>
        </optgroup>
      </select>
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

    <FactsPanel
      :world="world.slug"
      :entity="detail.entity"
      :facts="detail.facts"
      :suggestions="suggestions[detail.entity.kind] ?? { labels: [], common: [], values: {} }"
      :several="(label: string) => cards.several(detail!.entity.kind, label)"
      :chapter-titles="detail.chapter_titles"
      :timeline="cards.timeline"
      :as-of="asOf"
      :index-of="cards.indexOf"
      @changed="changed"
      @error="(m) => (error = m)"
    />

    <RelationsPanel
      :world="world.slug"
      :entity="detail.entity"
      :relationships="detail.relationships"
      :types="types"
      :names="cards.names"
      :timeline="cards.timeline"
      :as-of="asOf"
      :index-of="cards.indexOf"
      @changed="changed"
      @error="(m) => (error = m)"
    />

    <section v-if="kin.length" class="card family-worked-out" data-testid="family-worked-out">
      <div class="card-head">
        <h2>Family, worked out</h2>
        <span class="muted small">From the recorded parents, children and marriages{{ asOf !== null ? ", as of this chapter" : "" }}. To make one a relationship, record it above.</span>
      </div>
      <ul class="plain-list">
        <li v-for="k in kin" :key="k.id + k.relation" :class="`k-${k.who.kind}`">
          <span class="kin-word">{{ k.word }}</span> ·
          <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: k.id }, query: asOfId ? { asof: asOfId } : {} }">{{ k.who.name }}</RouterLink>
          <span v-if="k.path.length" class="muted small"> (via {{ k.path.join(" → ") }})</span>
        </li>
      </ul>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Notes</h2>
        <button v-if="!editingNotes" type="button" class="btn btn-sm" @click="(notes = detail!.entity.body), (editingNotes = true)">Edit</button>
      </div>
      <form v-if="editingNotes" class="form wide" @submit.prevent="(editingNotes = false), save({ body: notes })">
        <label for="e-body" class="visually-hidden">Notes</label>
        <textarea id="e-body" v-model="notes" class="capture-box" rows="10" />
        <div class="actions">
          <button class="btn btn-primary btn-sm" type="submit">Save</button>
          <button class="btn btn-sm" type="button" @click="editingNotes = false">Cancel</button>
        </div>
      </form>
      <p v-else-if="detail.entity.body" class="prose item-text">{{ detail.entity.body }}</p>
      <p v-else class="empty">No notes.</p>
    </section>

    <section v-if="detail.decisions.length" class="card">
      <div class="card-head"><h2>Decisions</h2></div>
      <ul class="rows" data-testid="entity-decisions">
        <li v-for="d in detail.decisions" :key="d.id">
          <span class="muted small">{{ d.decided_on }}</span>
          <span class="grow">{{ d.text }}</span>
          <span v-if="!d.tagged" class="muted small" title="Names it without being tagged">mentions</span>
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
