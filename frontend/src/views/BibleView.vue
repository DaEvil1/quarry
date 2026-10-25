<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { createEntity, listEntities } from "../bible";
import { readLastUsed } from "../lastUsed";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type Entity, type EntityKind } from "../types";
import { useCards } from "../world/cards";
import { filterText, groupBy, labelsOfKind, matches, norm, parseFilter, valuesAtEnd, type LabelReader, type ValueFilter } from "../world/labels";
import { eventTime } from "../world/eras";
import { SPECIES_COLUMN, speciesAtEnd } from "../world/species";
import { timeText, unitOf } from "../world/when";
import NotFoundView from "./NotFoundView.vue";

// The bible: every entry, or one kind of them (characters, places, …) as a table with their one-liners and the facts
// most of them have. With a book chosen, the entries it uses come first and the rest follow, dimmed, under
// "Elsewhere" (docs/SPEC.md §12.4). A kind's table filters by a fact's value and groups by any label (§12.6.2).
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const kind = computed(() => (route.params.kind ? (String(route.params.kind) as EntityKind) : null));
const kindInfo = computed(() => ENTITY_KINDS.find((k) => k.value === kind.value) ?? null);
const kindWord = (k: string) => (ENTITY_KINDS.find((x) => x.value === k)?.label ?? k).toLowerCase();
const entities = ref<Entity[]>([]);
const q = ref("");
const error = ref("");

const newName = ref("");
const newKind = ref<EntityKind>("character");
const busy = ref(false);
watch(kind, (k) => (newKind.value = k ?? "character"), { immediate: true });

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    entities.value = await listEntities(worldSlug.value);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(worldSlug, load, { immediate: true });
watch(worldSlug, (w) => void cards.load(w), { immediate: true });

// ---- the address: the book chosen, value filters, grouping ----
const setQuery = (changes: Record<string, string | string[] | undefined>) => void router.replace({ query: { ...route.query, ...changes } });
const projects = computed(() => world.value?.projects ?? []);
const severalBooks = computed(() => projects.value.length > 1);
// the book chosen: in the address, else the one last opened on this device
const book = computed(() => {
  if (!severalBooks.value) return "";
  const asked = route.query.book;
  if (typeof asked === "string") return projects.value.some((p) => p.slug === asked) ? asked : "";
  const last = readLastUsed();
  return last.world === worldSlug.value && last.project && projects.value.some((p) => p.slug === last.project) ? last.project : "";
});
const projectName = (slug: string) => projects.value.find((p) => p.slug === slug)?.name ?? slug;
const filters = computed<ValueFilter[]>(() => {
  const raw = route.query.f;
  const list = Array.isArray(raw) ? raw : raw ? [raw] : [];
  return list.map((x) => parseFilter(String(x))).filter((x): x is ValueFilter => !!x);
});
const groupLabel = computed(() => (typeof route.query.group === "string" ? route.query.group : ""));
function addFilter(f: ValueFilter) {
  if (filters.value.some((x) => norm(x.label) === norm(f.label) && norm(x.value) === norm(f.value))) return;
  setQuery({ f: [...filters.value, f].map(filterText) });
}
function dropFilter(f: ValueFilter) {
  setQuery({ f: filters.value.filter((x) => x !== f).map(filterText) });
}

const reader = computed<LabelReader>(() => ({
  several: (k, label) => cards.several(k, label),
  last: cards.lastPlace,
  indexOf: cards.indexOf,
}));

const shown = computed(() => {
  const needle = q.value.trim().toLowerCase();
  return entities.value.filter((e) => {
    // an entry of more than one kind is listed under each (docs/SPEC.md §14.8)
    if (kind.value && e.kind !== kind.value && !(e.also_kinds ?? []).includes(kind.value as EntityKind)) return false;
    if (needle && !e.name.toLowerCase().includes(needle) && !e.summary.toLowerCase().includes(needle) && !e.aliases.some((a) => a.toLowerCase().includes(needle))) return false;
    if (kind.value && filters.value.length) {
      const c = cards.byId.get(e.id);
      if (!c || !matches(c, filters.value, reader.value)) return false;
    }
    return true;
  });
});

// in the chosen book: named in its chapters, or in its own bible; else where it is used
const inBook = (e: Entity) => !book.value || e.project === book.value || e.named_in.includes(book.value);
function whereUsed(e: Entity): string {
  const others = e.named_in.filter((p) => p !== book.value);
  if (!others.length) return e.project && e.project !== book.value ? `in ${projectName(e.project)}'s bible, not named yet` : "not named yet";
  return others.length === 1 ? `only in ${projectName(others[0]!)}` : `in ${others.length} other books`;
}

// sorting: by name, or by a column clicked
const sortBy = ref<string>("name");
const sortDown = ref(false);
function sortOn(col: string) {
  if (sortBy.value === col) sortDown.value = !sortDown.value;
  else (sortBy.value = col), (sortDown.value = false);
}
const values = (e: Entity, label: string) => {
  const c = cards.byId.get(e.id);
  return c ? valuesAtEnd(c, label, label === SPECIES_COLUMN || cards.several(c.kind, label), reader.value.last, cards.indexOf) : [];
};
/** A fact recorded by when it began and nothing else ("born", with a time and no value): the time, read in the
 * column, so it isn't blank. Not a filter value. */
function timeOnly(e: Entity, label: string): { text: string; t: number | null } | null {
  if (label === SPECIES_COLUMN) return null;
  const c = cards.byId.get(e.id);
  const key = norm(label);
  const f = c?.facts.filter((x) => norm(x.label) === key && !x.value.trim() && (x.from_time != null || x.from)).at(-1);
  if (!f) return null;
  if (f.from_time != null) return { text: timeText({ time_at: f.from_time, time_approx: f.from_approx }, unitOf(world.value)), t: f.from_time };
  return { text: `from ${cards.chapterTitle(f.from!) ?? "a chapter"}`, t: null };
}
/** A column's heading: a fact label, or "Species" for what characters are (read from "is a", docs/SPEC.md §13.3). */
const heading = (label: string) => (label === SPECIES_COLUMN ? "Species" : label);
// the characters table gets a Species column once any character is recorded as being one
const hasSpecies = computed(() => kind.value === "character" && cards.cards.some((c) => c.kind === "character" && speciesAtEnd(c, null, cards.indexOf).length));
// the events table gets a When column (docs/SPEC.md §13.2.1) that sorts in happened order: times, then events in a
// chapter with no time (in book order), then outside time, then those not placed yet
const hasWhen = computed(() => kind.value === "event");
const chaptersById = computed(() => new Map(cards.timeline.map((c) => [c.id, c])));
function whenKey(e: Entity): number {
  const c = cards.byId.get(e.id);
  if (!c?.when) return Number.MAX_VALUE;
  if (c.when.outside) return 1e300;
  const t = eventTime(c, chaptersById.value);
  if (t) return t.t;
  return 1e299 + (chaptersById.value.get(c.when.chapter ?? "")?.index ?? 0);
}
function whenCell(e: Entity): { text: string; colour?: string } {
  const c = cards.byId.get(e.id);
  if (!c?.when) return { text: "" };
  if (c.whenText) return { text: c.whenText, colour: c.whenColour };
  return { text: c.when.chapter ? `in ${cards.chapterTitle(c.when.chapter) ?? "a chapter"}` : "" };
}
function sortKey(e: Entity): string | number {
  if (sortBy.value === "name") return e.name.toLowerCase();
  if (sortBy.value === "@when") return whenKey(e);
  if (sortBy.value === "summary") return e.summary.toLowerCase();
  if (sortBy.value === "level") return e.project ? projectName(e.project).toLowerCase() : "";
  if (sortBy.value === "#") return e.mention_count;
  const v = values(e, sortBy.value)[0];
  if (v === undefined) {
    const t = timeOnly(e, sortBy.value);
    if (t?.t != null) return t.t;
  }
  return (v ?? "￿").toLowerCase();
}
const sorted = (list: Entity[]) => {
  const out = [...list].sort((a, b) => {
    const x = sortKey(a);
    const y = sortKey(b);
    return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) || a.name.localeCompare(b.name);
  });
  return sortDown.value ? out.reverse() : out;
};

/** The table's sections: by value when grouping; else, with a book chosen, the book's entries and the rest. */
const sections = computed(() => {
  const list = shown.value;
  if (kind.value && groupLabel.value) {
    return groupBy(list, (e) => cards.byId.get(e.id), groupLabel.value, reader.value).map((g) => ({
      key: g.value ?? "",
      title: g.value ?? `no ${heading(groupLabel.value).toLowerCase()}`,
      value: g.value,
      elsewhere: false,
      items: sorted(g.items),
    }));
  }
  if (!book.value) return [{ key: "all", title: "", value: null, elsewhere: false, items: sorted(list) }];
  return [
    { key: "in", title: "In this book", value: null, elsewhere: false, items: sorted(list.filter(inBook)) },
    { key: "else", title: "Elsewhere", value: null, elsewhere: true, items: sorted(list.filter((e) => !inBook(e))) },
  ].filter((s) => s.items.length);
});

const groups = computed(() =>
  ENTITY_KINDS.map((k) => ({ ...k, items: sorted(shown.value.filter((e) => e.kind === k.value)).sort((a, b) => Number(!inBook(a)) - Number(!inBook(b))) })).filter((g) => g.items.length),
);

/** On a kind's page: up to three fact labels that at least two of its entries have, as extra columns, and any label a
 * filter or the grouping uses. */
const kindLabels = computed(() => (kind.value ? labelsOfKind(cards.cards, kind.value) : []));
const columns = computed(() => {
  if (!kind.value) return [];
  const top = kindLabels.value.filter((l) => l.count >= 2).slice(0, 3).map((l) => l.label);
  for (const l of [...filters.value.map((f) => f.label), groupLabel.value]) if (l && l !== SPECIES_COLUMN && !top.some((x) => norm(x) === norm(l))) top.push(l);
  if (hasSpecies.value) top.push(SPECIES_COLUMN);
  return top;
});

async function add() {
  busy.value = true;
  error.value = "";
  try {
    const e = await createEntity(worldSlug.value, { name: newName.value, kind: newKind.value });
    newName.value = "";
    void cards.refresh(worldSlug.value);
    await router.push({ name: "entity", params: { world: worldSlug.value, id: e.id } });
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <NotFoundView v-if="!world || (kind && !kindInfo)" what="world" />
  <template v-else>
    <div class="page-head" :class="kind ? `k-${kind}` : ''">
      <div>
        <div class="crumbs">
          <RouterLink v-if="kind" :to="{ name: 'bible', params: { world: world.slug } }">Bible</RouterLink>
          <template v-else>{{ world.name }}</template>
        </div>
        <h1><span v-if="kind" class="kdot" />{{ kindInfo?.plural ?? "Bible" }}</h1>
        <p v-if="!kind" class="muted">Everything in this world's bible, shared by every project, and each project's own.</p>
      </div>
      <div class="actions">
        <RouterLink class="btn btn-sm" :to="{ name: 'labels', params: { world: world.slug } }" data-testid="labels-link">Labels</RouterLink>
        <RouterLink class="btn btn-sm" :to="{ name: 'relation-types', params: { world: world.slug } }">Kinds of relationship</RouterLink>
      </div>
    </div>

    <form class="card form wide" @submit.prevent="add">
      <div class="actions">
        <div class="field grow">
          <label for="new-entity">New entry</label>
          <input id="new-entity" v-model="newName" type="text" maxlength="200" required placeholder="Name" />
        </div>
        <div class="field">
          <label for="new-kind">Kind</label>
          <select id="new-kind" v-model="newKind">
            <option v-for="k in ENTITY_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </div>
        <button class="btn btn-primary" type="submit" :disabled="busy">Add to the bible</button>
      </div>
    </form>

    <div class="toolbar">
      <div class="field grow">
        <label for="bible-search" class="visually-hidden">Search</label>
        <input id="bible-search" v-model="q" type="search" class="filter search" placeholder="Search names, spellings and one-liners" />
      </div>
      <label v-if="severalBooks" class="small muted">Book
        <select class="filter" :value="book" data-testid="bible-book" @change="setQuery({ book: ($event.target as HTMLSelectElement).value })">
          <option value="">every book</option>
          <option v-for="p in projects" :key="p.id" :value="p.slug">{{ p.name }}</option>
        </select>
      </label>
      <label v-if="kind && (kindLabels.length || hasSpecies)" class="small muted">Group by
        <select class="filter" :value="groupLabel" data-testid="group-by" @change="setQuery({ group: ($event.target as HTMLSelectElement).value || undefined })">
          <option value="">nothing</option>
          <option v-for="l in kindLabels" :key="l.label" :value="l.label">{{ l.label }}</option>
          <option v-if="hasSpecies" :value="SPECIES_COLUMN">species</option>
        </select>
      </label>
    </div>
    <div v-if="kind && filters.length" class="chips filter-chips" data-testid="filters">
      <span v-for="f in filters" :key="filterText(f)" class="chip static tag">
        {{ heading(f.label) }}: {{ f.value }}<button type="button" class="chip-x" :aria-label="`Remove the filter ${heading(f.label)}: ${f.value}`" @click="dropFilter(f)">×</button>
      </span>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <section v-if="kind && shown.length" class="card table-card" :class="`k-${kind}`">
      <table class="bible-table" data-testid="bible-list">
        <thead>
          <tr>
            <th><button type="button" class="th-sort" @click="sortOn('name')">Name</button></th>
            <th><button type="button" class="th-sort" @click="sortOn('summary')">In one line</button></th>
            <th v-if="severalBooks"><button type="button" class="th-sort" @click="sortOn('level')">Level</button></th>
            <th v-if="hasWhen"><button type="button" class="th-sort" data-testid="sort-when" @click="sortOn('@when')">When</button></th>
            <th v-for="c in columns" :key="c"><button type="button" class="th-sort" @click="sortOn(c)">{{ heading(c) }}</button></th>
            <th class="num" title="Mentions"><button type="button" class="th-sort" @click="sortOn('#')">#</button></th>
          </tr>
        </thead>
        <tbody v-for="s in sections" :key="s.key" :class="{ elsewhere: s.elsewhere }" :data-testid="`section-${s.key}`">
          <tr v-if="s.title" class="section-head">
            <th :colspan="4 + columns.length + (hasWhen ? 1 : 0)">
              <button v-if="s.value" type="button" class="linkish" :title="`Only ${heading(groupLabel)}: ${s.value}`" @click="addFilter({ label: groupLabel, value: s.value })">{{ s.title }}</button>
              <template v-else>{{ s.title }}</template>
              <span class="muted"> ({{ s.items.length }})</span>
            </th>
          </tr>
          <tr v-for="e in s.items" :key="e.id" :class="{ dim: !inBook(e) }">
            <td>
              <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
              <span v-if="kind && e.kind !== kind" class="pill small" data-testid="also-tag">{{ kindWord(e.kind) }}, also a {{ kindWord(kind) }}</span>
              <div v-if="e.aliases.length" class="muted small">{{ e.aliases.join(", ") }}</div>
              <div v-if="!inBook(e)" class="small where-used" data-testid="where-used">{{ whereUsed(e) }}</div>
            </td>
            <td class="muted">{{ e.summary }}</td>
            <td v-if="severalBooks" class="small">{{ e.project ? projectName(e.project) : "World" }}</td>
            <td v-if="hasWhen" class="small" data-testid="when-cell"><span :class="whenCell(e).colour ? `era-${whenCell(e).colour} era-tint` : 'muted'">{{ whenCell(e).text }}</span></td>
            <td v-for="c in columns" :key="c" class="fact-cell">
              <button v-for="v in values(e, c)" :key="v" type="button" class="value-link" :title="`Only ${heading(c)}: ${v}`" @click="addFilter({ label: c, value: v })">{{ v }}</button>
              <span v-if="!values(e, c).length && timeOnly(e, c)" class="small" data-testid="fact-time">{{ timeOnly(e, c)!.text }}</span>
            </td>
            <td class="num muted">{{ e.mention_count }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <template v-else-if="!kind">
      <section v-for="g in groups" :key="g.value" class="card" :class="`k-${g.value}`">
        <h2 class="small muted">
          <RouterLink :to="{ name: 'bible-kind', params: { world: world.slug, kind: g.value }, query: book ? { book } : {} }"><span class="kdot" />{{ g.plural }}</RouterLink>
        </h2>
        <ul class="rows" data-testid="bible-list">
          <li v-for="e in g.items" :key="e.id" :class="{ dim: !inBook(e) }">
            <RouterLink class="kname" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink>
            <span class="grow muted small ellipsis">{{ e.summary }}</span>
            <span v-if="!inBook(e)" class="small where-used">{{ whereUsed(e) }}</span>
            <span v-if="e.aliases.length" class="muted small">also {{ e.aliases.join(", ") }}</span>
            <span class="pill" :title="`${e.mention_count} mentions`">{{ e.mention_count }}</span>
          </li>
        </ul>
      </section>
    </template>

    <p v-if="!shown.length && !error" class="empty">
      {{ entities.length && (q || !kind || filters.length) ? "Nothing matches." : kind ? `No ${kindInfo?.plural.toLowerCase()} yet.` : "The bible is empty. Add the first name above." }}
    </p>
  </template>
</template>
