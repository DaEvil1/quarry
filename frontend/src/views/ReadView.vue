<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import type { LocalChapter } from "../localdb";
import { localChapters, syncWorld } from "../offline";
import { useSession } from "../stores/session";
import { asIfAccepted } from "../world/asif";
import NotFoundView from "./NotFoundView.vue";

// Reading the book read-only, as if an experiment were accepted (docs/SPEC.md §13.6.1): its drafts in place of the
// range they would replace, or at the place they add at. From the chapters kept on the device, so offline too.
const route = useRoute();
const session = useSession();
const world = computed(() => session.world(String(route.params.world)));
const project = computed(() => (world.value ? session.project(world.value.slug, String(route.params.project)) : undefined));
const item = computed(() => (typeof route.query.as_if === "string" ? route.query.as_if : null));
const chapters = ref<LocalChapter[] | null>(null);

async function load() {
  const w = world.value?.slug;
  if (!w) return;
  await syncWorld(w).catch(() => false);
  chapters.value = await localChapters(w);
}
watch(world, load, { immediate: true });

const book = computed(() => (chapters.value && project.value ? asIfAccepted(chapters.value, project.value.slug, item.value) : []));
const title = computed(() => book.value.find((c) => c.draft)?.experiment?.title ?? "");
// the prose only: margin notes (%% lines) stay out, as in the compiled manuscript
const paras = (body: string) => body.split("\n").filter((l) => l.trim() && !/^[ \t]*%%/.test(l));
</script>

<template>
  <NotFoundView v-if="!world || !project" what="project" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'project', params: { world: world.slug, project: project.slug } }">{{ project.name }}</RouterLink>
        </div>
        <h1>{{ project.name }}</h1>
        <p v-if="item" class="muted" data-testid="read-as-if-line">Read as if “{{ title }}” were accepted: its drafts in place, read-only.</p>
      </div>
    </div>
    <p v-if="chapters === null" class="muted">Loading…</p>
    <article v-for="(c, i) in book" :key="c.id" class="card reading" :class="{ draft: c.draft }" data-testid="read-chapter">
      <h2>
        <span class="muted small">{{ i + 1 }}</span>
        <RouterLink :to="{ name: 'chapter', params: { world: world.slug, id: c.id } }">{{ c.title }}</RouterLink>
        <span v-if="c.draft" class="pill accent">draft</span>
      </h2>
      <p v-for="(p, j) in paras(c.body)" :key="j" class="prose">{{ p }}</p>
    </article>
  </template>
</template>
