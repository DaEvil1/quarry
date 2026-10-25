<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import DecisionFollowups from "../components/DecisionFollowups.vue";
import EntityPicker from "../components/EntityPicker.vue";
import ProjectFilter from "../components/ProjectFilter.vue";
import { journalDay, planning, type PlanningDecision, type PlanningItem } from "../journal";
import type { LocalChapter, LocalEntry } from "../localdb";
import { localChapters, localJournal, syncWorld } from "../offline";
import { useSession } from "../stores/session";
import type { EntityRef } from "../types";
import { useCards } from "../world/cards";
import { asIfAccepted } from "../world/asif";
import { planningCount, planningReading, type PlanningKind } from "../world/planning";
import { segments, thread, threadCount, unsettledLine, type Gap, type Para, type ThreadChapter } from "../world/thread";
import NotFoundView from "./NotFoundView.vue";

// Reading one entry's thread (docs/SPEC.md §11.4): every paragraph (or chapter) that names it, in story order across
// the world's projects, read-only, with the margin notes beside them. Built on this device from the offline copy and
// the name matcher, so it works on the phone without a network. "With…" narrows it to what names a second entry too.
// "The planning" reads the entry through the Journal, items and decisions instead, oldest first (docs/SPEC.md §14.2);
// the book and the planning are never mixed into one reading.
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const id = computed(() => String(route.params.id));
const withId = computed(() => (typeof route.query.with === "string" && route.query.with !== id.value ? route.query.with : null));
const mode = computed<"paragraphs" | "chapters">(() => (route.query.mode === "chapters" ? "chapters" : "paragraphs"));
const inPlanning = computed(() => route.query.in === "planning");
const all = computed(() => route.query.all === "1");
const entry = computed(() => cards.byId.get(id.value));
const other = computed(() => (withId.value ? cards.byId.get(withId.value) : undefined));
const ids = computed(() => [id.value, ...(withId.value ? [withId.value] : [])]);

const chapters = ref<LocalChapter[] | null>(null);
const synced = ref(true);
const picking = ref(false);
const expanded = ref(new Set<string>());

const entries = ref<LocalEntry[]>([]);
async function load() {
  const w = worldSlug.value;
  void cards.load(w);
  synced.value = await syncWorld(w).catch(() => false);
  const [local, journal] = await Promise.all([localChapters(w), localJournal(w)]);
  if (w !== worldSlug.value) return;
  chapters.value = local;
  entries.value = journal;
}
watch(worldSlug, load, { immediate: true });

// ---- the planning (docs/SPEC.md §14.2): journal entries here, items and decisions from the server ----
const planned = ref<{ items: PlanningItem[]; decisions: PlanningDecision[] } | null>(null);
const planningOffline = ref(false);
const kinds = ref(new Set<PlanningKind>(["journal", "item", "decision"]));
const planningProject = ref("");
async function loadPlanning() {
  if (!inPlanning.value) return;
  try {
    planned.value = await planning(worldSlug.value, ids.value);
    planningOffline.value = false;
  } catch {
    planned.value = { items: [], decisions: [] };
    planningOffline.value = true;
  }
}
watch([inPlanning, ids], loadPlanning, { immediate: true });
function toggleKind(k: PlanningKind) {
  const next = new Set(kinds.value);
  if (next.has(k)) next.delete(k);
  else next.add(k);
  kinds.value = next;
}
const planningRead = computed(() => {
  void cards.version;
  return planningReading({
    entries: entries.value,
    items: planned.value?.items ?? [],
    decisions: planned.value?.decisions ?? [],
    matcher: cards.matcher(),
    ids: ids.value,
    mode: route.query.mode === "entries" ? "entries" : "paragraphs",
    kinds: kinds.value,
    project: planningProject.value === "-" ? "" : planningProject.value,
    from: typeof route.query.from === "string" ? route.query.from : undefined,
  });
});
const planningHeading = computed(() => planningCount([entry.value?.name ?? "…", ...(other.value ? [other.value.name] : [])], planningRead.value.counts));
const entryAt = (entryId: string, from: number) => ({ name: "journal-entry", params: { world: worldSlug.value, id: entryId }, query: { at: String(from) } });

/** The chapters in story order: projects in order, then chapters in theirs; experiments and retired ones after the
 * story, labelled, when asked for. */
const ordered = computed<(ThreadChapter & { label?: string })[]>(() => {
  const list = chapters.value ?? [];
  const projects = [...(world.value?.projects ?? [])].sort((a, b) => a.position - b.position);
  const name = new Map(projects.map((p) => [p.slug, p.name]));
  const rank = new Map(projects.map((p, i) => [p.slug, i]));
  const sort = (xs: typeof list) => [...xs].sort((a, b) => (rank.get(a.project) ?? 99) - (rank.get(b.project) ?? 99) || a.position - b.position);
  const as = (c: (typeof list)[number], label?: string) => ({
    id: c.id, title: c.title, body: c.body, state: c.state, project: c.project, project_name: name.get(c.project) ?? c.project, label,
  });
  // "as if accepted" (docs/SPEC.md §13.6.1): an experiment's drafts in place of its range
  const item = typeof route.query.as_if === "string" ? route.query.as_if : null;
  const story = item
    ? projects.flatMap((p) => asIfAccepted(list, p.slug, item)).map((c) => as(c, c.draft ? "draft" : undefined))
    : sort(list.filter((c) => c.state === "current")).map((c) => as(c));
  if (!all.value) return story;
  return [
    ...story,
    ...sort(list.filter((c) => c.state === "experiment")).map((c) => as(c, "experiment")),
    ...sort(list.filter((c) => c.state === "retired")).map((c) => as(c, "retired")),
  ];
});

const reading = computed(() => {
  void cards.version;
  return thread(ordered.value, cards.matcher(), ids.value, mode.value);
});
/** the chapters and the world's names are both here (until then a count would read 0) */
const ready = computed(() => chapters.value !== null && cards.world === worldSlug.value && !!entry.value);
const heading = computed(() =>
  threadCount([entry.value?.name ?? "…", ...(other.value ? [other.value.name] : [])], reading.value.paragraphs, reading.value.chapters),
);

function set(query: Record<string, string | undefined>) {
  void router.replace({ query: { ...route.query, ...query } });
}
function pick(e: EntityRef) {
  picking.value = false;
  set({ with: e.id });
}
const strong = (entityId: string) => ids.value.includes(entityId);
const at = (chapterId: string, from: number) => ({ name: "chapter", params: { world: worldSlug.value, id: chapterId }, query: { at: String(from) } });
const gapKey = (chapterId: string, g: Gap) => `${chapterId}:${g.paras[0]?.from}`;
function openGap(chapterId: string, g: Gap) {
  expanded.value = new Set([...expanded.value, gapKey(chapterId, g)]);
}
const projectBreak = (i: number) => i === 0 || reading.value.parts[i - 1]!.chapter.project !== reading.value.parts[i]!.chapter.project;
const labelOf = (c: ThreadChapter) => ordered.value.find((x) => x.id === c.id)?.label;
const paraClass = (p: Para) => ({ margin: p.margin, hit: p.hit });
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <div v-else class="thread-page">
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'entity', params: { world: world.slug, id } }">{{ entry?.name ?? "Entry" }}</RouterLink>
          · Reading
        </div>
        <div class="tabs" role="tablist" aria-label="Read through">
          <button type="button" role="tab" class="tab" :aria-selected="!inPlanning" data-testid="read-book" @click="set({ in: undefined, mode: undefined })">The book</button>
          <button type="button" role="tab" class="tab" :aria-selected="inPlanning" data-testid="read-planning" @click="set({ in: 'planning', mode: undefined })">The planning</button>
        </div>
        <template v-if="inPlanning">
          <h1 v-if="ready" data-testid="planning-count">{{ planningHeading }}</h1>
          <p v-if="ready && planningRead.counts.unsettled" class="small muted" data-testid="planning-unsettled">{{ unsettledLine(planningRead.counts.unsettled) }}</p>
          <h1 v-else>Reading…</h1>
          <p v-if="planningOffline" class="small muted" data-testid="planning-offline">Items and decisions need the network.</p>
        </template>
        <template v-else>
          <h1 v-if="ready" data-testid="thread-count">{{ heading }}</h1>
          <p v-if="ready && reading.unsettled" class="small muted" data-testid="thread-unsettled">{{ unsettledLine(reading.unsettled) }}</p>
          <h1 v-else>Reading…</h1>
          <p v-if="!synced" class="small muted" data-testid="thread-offline">Offline: read from the chapters kept on this device.</p>
        </template>
      </div>
      <div v-if="inPlanning" class="actions thread-tools">
        <div class="tabs" role="tablist" aria-label="Read by">
          <button type="button" role="tab" class="tab" :aria-selected="route.query.mode !== 'entries'" @click="set({ mode: undefined })">Paragraphs</button>
          <button type="button" role="tab" class="tab" :aria-selected="route.query.mode === 'entries'" @click="set({ mode: 'entries' })">Entries</button>
        </div>
        <div class="qrow" data-testid="planning-kinds">
          <button v-for="k in (['journal', 'item', 'decision'] as const)" :key="k" type="button" class="qchip" :class="{ on: kinds.has(k) }" :aria-pressed="kinds.has(k)" @click="toggleKind(k)">{{ k === "journal" ? "journal entries" : k === "item" ? "items" : "decisions" }}</button>
        </div>
        <ProjectFilter v-model="planningProject" :world="world" />
      </div>
      <div v-else class="actions thread-tools">
        <div class="tabs" role="tablist" aria-label="Read by">
          <button type="button" role="tab" class="tab" :aria-selected="mode === 'paragraphs'" @click="set({ mode: undefined })">Paragraphs</button>
          <button type="button" role="tab" class="tab" :aria-selected="mode === 'chapters'" @click="set({ mode: 'chapters' })">Chapters</button>
        </div>
        <label class="check small"><input type="checkbox" :checked="all" @change="set({ all: ($event.target as HTMLInputElement).checked ? '1' : undefined })" /> Experiments and retired</label>
      </div>
    </div>

    <div class="thread-with actions">
      <template v-if="other">
        <span class="small muted">With</span>
        <span class="chip static kname" :class="`k-${other.kind}`">
          {{ other.name }}<button type="button" class="chip-x" :aria-label="`Stop reading with ${other.name}`" @click="set({ with: undefined })">×</button>
        </span>
      </template>
      <template v-else-if="picking">
        <EntityPicker :entities="cards.names" :exclude="[id]" placeholder="Read together with…" autofocus @pick="pick" @cancel="picking = false" />
      </template>
      <button v-else type="button" class="btn btn-sm" @click="picking = true">With…</button>
    </div>

    <template v-if="inPlanning">
      <p v-if="ready && !planningRead.lines.length" class="empty">Nothing in the planning names {{ other ? "both" : "it" }} yet.</p>
      <template v-for="(l, i) in ready ? planningRead.lines : []" :key="i">
        <h2 v-if="l.kind === 'year'" class="planning-year" data-testid="planning-year">{{ l.year }}</h2>
        <p v-else-if="l.kind === 'gap-years'" class="muted small planning-gap" data-testid="planning-gap">· {{ l.years }} {{ l.years === 1 ? "year" : "years" }} ·</p>
        <article v-else-if="l.kind === 'journal'" class="card thread-chapter" data-testid="planning-entry">
          <h3 class="thread-title">
            <RouterLink :to="entryAt(l.entry.id, 0)">{{ journalDay(l.entry.entry_date) }}<template v-if="l.entry.title"> · {{ l.entry.title }}</template></RouterLink>
            <span class="muted small">{{ l.count }} {{ l.count === 1 ? "paragraph" : "paragraphs" }}</span>
          </h3>
          <template v-for="b in l.blocks" :key="b.kind === 'para' ? b.from : gapKey(l.entry.id, b)">
            <RouterLink v-if="b.kind === 'para'" :to="entryAt(l.entry.id, b.from)" class="thread-para prose" :class="{ hit: b.hit }" data-testid="planning-para"
              ><template v-for="(s, k) in segments(b)" :key="k"
                ><span v-if="s.hit" class="kname" :class="[`k-${s.hit.entityKind}`, { 'thread-self': strong(s.hit.entityId) }]">{{ s.text }}</span
                ><template v-else>{{ s.text }}</template></template
              ></RouterLink>
            <template v-else-if="expanded.has(gapKey(l.entry.id, b))">
              <RouterLink v-for="p in b.paras" :key="p.from" :to="entryAt(l.entry.id, p.from)" class="thread-para prose between">{{ p.text }}</RouterLink>
            </template>
            <button v-else type="button" class="thread-gap linkish" @click="openGap(l.entry.id, b)">⋯ {{ b.paras.length }} {{ b.paras.length === 1 ? "paragraph" : "paragraphs" }}</button>
          </template>
        </article>
        <article v-else-if="l.kind === 'item'" class="card thread-chapter planning-item" data-testid="planning-item">
          <div class="muted small">
            {{ journalDay(l.date) }} · {{ l.item.kind }} · {{ l.item.status }}
            <span v-if="l.tagged" class="pill" data-testid="tagged">tagged</span>
          </div>
          <RouterLink :to="{ name: 'item', params: { world: world.slug, id: l.item.id } }" class="prose">{{ l.item.title || l.item.body }}</RouterLink>
          <p v-if="l.item.closed_note" class="muted small">{{ l.item.closed_note }}</p>
        </article>
        <article v-else class="card thread-chapter planning-decision" data-testid="planning-decision">
          <div class="muted small">
            {{ journalDay(l.date) }} · decision
            <span v-if="l.tagged" class="pill" data-testid="tagged">tagged</span>
          </div>
          <div class="fu-line actions">
            <RouterLink :to="{ name: 'decisions', params: { world: world.slug }, hash: `#d-${l.decision.id}` }" class="prose">{{ l.decision.text }}</RouterLink>
            <DecisionFollowups :world="world.slug" :decision="l.decision" @counts="(c) => (l.decision.followups = c)" />
          </div>
        </article>
      </template>
    </template>

    <p v-if="!inPlanning && ready && !reading.parts.length" class="empty">
      {{ chapters?.length ? "No chapter names " + (other ? "both." : "it yet.") : "No chapters on this device yet; open the world once with a connection." }}
    </p>

    <template v-for="(part, i) in ready && !inPlanning ? reading.parts : []" :key="part.chapter.id">
      <h2 v-if="projectBreak(i)" class="small muted thread-project">{{ part.chapter.project_name }}</h2>
      <article class="card thread-chapter" data-testid="thread-chapter">
        <h3 class="thread-title">
          <RouterLink :to="at(part.chapter.id, 0)">{{ part.chapter.title }}</RouterLink>
          <span v-if="labelOf(part.chapter)" class="pill accent">{{ labelOf(part.chapter) }}</span>
          <span class="muted small">{{ part.count }} {{ part.count === 1 ? "paragraph" : "paragraphs" }}</span>
        </h3>
        <template v-for="b in part.blocks" :key="b.kind === 'para' ? b.from : gapKey(part.chapter.id, b)">
          <RouterLink v-if="b.kind === 'para'" :to="at(part.chapter.id, b.from)" class="thread-para prose" :class="paraClass(b)" data-testid="thread-para"
            ><template v-for="(s, k) in segments(b)" :key="k"
              ><span v-if="s.hit" class="kname" :class="[`k-${s.hit.entityKind}`, { 'thread-self': strong(s.hit.entityId) }]">{{ s.text }}</span
              ><template v-else>{{ s.text }}</template></template
            ></RouterLink>
          <template v-else-if="expanded.has(gapKey(part.chapter.id, b))">
            <RouterLink v-for="p in b.paras" :key="p.from" :to="at(part.chapter.id, p.from)" class="thread-para prose between" :class="paraClass(p)"
              ><template v-for="(s, k) in segments(p)" :key="k"
                ><span v-if="s.hit" class="kname" :class="`k-${s.hit.entityKind}`">{{ s.text }}</span><template v-else>{{ s.text }}</template></template
              ></RouterLink>
          </template>
          <button v-else type="button" class="thread-gap linkish" data-testid="thread-gap" @click="openGap(part.chapter.id, b)">
            ⋯ {{ b.paras.length }} {{ b.paras.length === 1 ? "paragraph" : "paragraphs" }}
          </button>
        </template>
      </article>
    </template>
  </div>
</template>
