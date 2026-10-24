<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import EntityPicker from "../components/EntityPicker.vue";
import type { LocalChapter } from "../localdb";
import { localChapters, syncWorld } from "../offline";
import { useSession } from "../stores/session";
import type { EntityRef } from "../types";
import { useCards } from "../world/cards";
import { segments, thread, threadCount, type Gap, type Para, type ThreadChapter } from "../world/thread";
import NotFoundView from "./NotFoundView.vue";

// Reading one entry's thread (docs/SPEC.md §11.4): every paragraph (or chapter) that names it, in story order across
// the world's projects, read-only, with the margin notes beside them. Built on this device from the offline copy and
// the name matcher, so it works on the phone without a network. "With…" narrows it to what names a second entry too.
const route = useRoute();
const router = useRouter();
const session = useSession();
const cards = useCards();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const id = computed(() => String(route.params.id));
const withId = computed(() => (typeof route.query.with === "string" && route.query.with !== id.value ? route.query.with : null));
const mode = computed<"paragraphs" | "chapters">(() => (route.query.mode === "chapters" ? "chapters" : "paragraphs"));
const all = computed(() => route.query.all === "1");
const entry = computed(() => cards.byId.get(id.value));
const other = computed(() => (withId.value ? cards.byId.get(withId.value) : undefined));
const ids = computed(() => [id.value, ...(withId.value ? [withId.value] : [])]);

const chapters = ref<LocalChapter[] | null>(null);
const synced = ref(true);
const picking = ref(false);
const expanded = ref(new Set<string>());

async function load() {
  const w = worldSlug.value;
  void cards.load(w);
  synced.value = await syncWorld(w).catch(() => false);
  const local = await localChapters(w);
  if (w === worldSlug.value) chapters.value = local;
}
watch(worldSlug, load, { immediate: true });

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
  const story = sort(list.filter((c) => c.state === "current")).map((c) => as(c));
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
        <h1 data-testid="thread-count">{{ heading }}</h1>
        <p v-if="!synced" class="small muted" data-testid="thread-offline">Offline: read from the chapters kept on this device.</p>
      </div>
      <div class="actions thread-tools">
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

    <p v-if="chapters === null" class="muted">Reading…</p>
    <p v-else-if="!reading.parts.length" class="empty">
      {{ chapters.length ? "No chapter names " + (other ? "both." : "it yet.") : "No chapters on this device yet; open the world once with a connection." }}
    </p>

    <template v-for="(part, i) in reading.parts" :key="part.chapter.id">
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
