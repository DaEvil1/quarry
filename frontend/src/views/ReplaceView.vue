<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { unreachable } from "../api";
import UndoToast from "../components/UndoToast.vue";
import { findInChapters, replaceInChapters, undoReplace, type FindOptions, type FoundChapter, type Replaced } from "../manuscript";
import { sendDrafts } from "../offline";
import { useSession } from "../stores/session";
import NotFoundView from "./NotFoundView.vue";

// Find and replace across chapters (docs/SPEC.md §11.7): plain text, current chapters and experiments (margin notes
// included, Salvage left alone), a preview of every hit to tick and untick, then one replace on the server that
// checkpoints each chapter first and skips any that changed since the preview. Undo puts them back. Needs the network.
const route = useRoute();
const router = useRouter();
const session = useSession();
const world = computed(() => session.world(String(route.params.world)));
const project = computed(() => (world.value ? session.project(world.value.slug, String(route.params.project)) : undefined));

const q = (k: string) => (typeof route.query[k] === "string" ? (route.query[k] as string) : "");
const find = ref(q("find"));
const replacement = ref(q("replace"));
const matchCase = ref(q("case") !== "0");
const wholeWords = ref(q("whole") !== "0");
const scope = ref<"project" | "world">(q("scope") === "world" ? "world" : "project");

const found = ref<FoundChapter[] | null>(null);
const chosen = ref(new Map<string, Set<number>>());
const busy = ref(false);
const error = ref("");
const offline = ref(false);
const done = ref<Replaced | null>(null);
const undone = ref("");
const toast = ref<string | null>(null);

const options = (): FindOptions => ({ find: find.value, match_case: matchCase.value, whole_words: wholeWords.value, scope: scope.value });

/** Send what this device still holds, then look. */
async function preview() {
  const w = world.value;
  const p = project.value;
  if (!w || !p) return;
  error.value = "";
  offline.value = false;
  void router.replace({
    query: {
      find: find.value || undefined,
      replace: replacement.value || undefined,
      case: matchCase.value ? undefined : "0",
      whole: wholeWords.value ? undefined : "0",
      scope: scope.value === "world" ? "world" : undefined,
    },
  });
  if (!find.value) {
    found.value = null;
    return;
  }
  busy.value = true;
  try {
    await sendDrafts(w.slug);
    const r = await findInChapters(w.slug, p.slug, options());
    found.value = r.chapters;
    chosen.value = new Map(r.chapters.map((c) => [c.id, new Set(c.hits.map((h) => h.start))]));
  } catch (e) {
    if (unreachable(e)) offline.value = true;
    else error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
let timer: ReturnType<typeof setTimeout> | undefined;
watch([find, matchCase, wholeWords, scope], () => {
  clearTimeout(timer);
  timer = setTimeout(preview, 350);
});
watch(project, preview, { immediate: true });

const hitCount = computed(() => [...chosen.value.values()].reduce((n, s) => n + s.size, 0));
const chapterCount = computed(() => [...chosen.value.values()].filter((s) => s.size).length);
const total = computed(() => found.value?.reduce((n, c) => n + c.hits.length, 0) ?? 0);
const verb = computed(() => (replacement.value ? "Replace" : "Delete"));
const label = computed(() => `${verb.value} ${hitCount.value} in ${chapterCount.value} ${chapterCount.value === 1 ? "chapter" : "chapters"}`);

function toggleHit(c: FoundChapter, start: number) {
  const set = new Set(chosen.value.get(c.id));
  if (set.has(start)) set.delete(start);
  else set.add(start);
  chosen.value = new Map(chosen.value).set(c.id, set);
}
function toggleChapter(c: FoundChapter) {
  const on = (chosen.value.get(c.id)?.size ?? 0) > 0;
  chosen.value = new Map(chosen.value).set(c.id, new Set(on ? [] : c.hits.map((h) => h.start)));
}

async function replace() {
  const w = world.value;
  const p = project.value;
  if (!w || !p || !found.value || !hitCount.value) return;
  if (!replacement.value && !confirm(`Delete “${find.value}” ${hitCount.value} ${hitCount.value === 1 ? "time" : "times"}? Each chapter gets a checkpoint first, and Undo puts them back.`)) return;
  busy.value = true;
  error.value = "";
  undone.value = "";
  try {
    const chapters = found.value
      .map((c) => ({ id: c.id, version: c.version, hits: [...(chosen.value.get(c.id) ?? [])] }))
      .filter((c) => c.hits.length);
    done.value = await replaceInChapters(w.slug, p.slug, { ...options(), replace: replacement.value, chapters });
    toast.value = `${replacement.value ? "Replaced" : "Deleted"} ${done.value.replaced} in ${done.value.chapters.length} ${done.value.chapters.length === 1 ? "chapter" : "chapters"}`;
    await preview();
  } catch (e) {
    if (unreachable(e)) offline.value = true;
    else error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}

async function undo() {
  const w = world.value;
  const p = project.value;
  if (!w || !p || !done.value) return;
  const r = await undoReplace(w.slug, p.slug, done.value);
  undone.value =
    `Put back ${r.restored.length} ${r.restored.length === 1 ? "chapter" : "chapters"}.` +
    (r.skipped.length ? ` Left alone, changed since: ${r.skipped.map((s) => s.title).join(", ")}.` : "");
  done.value = null;
  toast.value = null;
  await preview();
}

const at = (c: FoundChapter, start: number) => ({ name: "chapter", params: { world: world.value!.slug, id: c.id }, query: { at: String(start) } });
const projectBreak = (i: number) => scope.value === "world" && (i === 0 || found.value![i - 1]!.project !== found.value![i]!.project);
</script>

<template>
  <NotFoundView v-if="!world || !project" what="project" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'project', params: { world: world.slug, project: project.slug } }">{{ project.name }}</RouterLink>
        </div>
        <h1>Find and replace</h1>
        <p class="muted">In every chapter and experiment, margin notes included. Salvage is left as it was.</p>
      </div>
    </div>

    <form class="card form wide replace-form" @submit.prevent="preview">
      <div class="actions">
        <div class="field grow">
          <label for="find">Find</label>
          <input id="find" v-model="find" type="text" maxlength="200" autocomplete="off" spellcheck="false" />
        </div>
        <div class="field grow">
          <label for="replace-with">Replace with</label>
          <input id="replace-with" v-model="replacement" type="text" maxlength="200" autocomplete="off" spellcheck="false" />
        </div>
      </div>
      <div class="actions">
        <label class="check small"><input v-model="matchCase" type="checkbox" /> Match capitals</label>
        <label class="check small"><input v-model="wholeWords" type="checkbox" /> Whole words</label>
        <label class="check small"><input v-model="scope" type="radio" value="project" /> {{ project.name }}</label>
        <label class="check small"><input v-model="scope" type="radio" value="world" /> Every project in {{ world.name }}</label>
      </div>
    </form>

    <div v-if="offline" class="notice offline" role="status" data-testid="replace-offline">Find and replace needs the network. Nothing was changed.</div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <div v-if="done" class="notice ok" role="status" data-testid="replace-done">
      {{ done.replaced }} {{ done.replaced === 1 ? "hit" : "hits" }} {{ replacement ? "replaced" : "deleted" }} in {{ done.chapters.length }}
      {{ done.chapters.length === 1 ? "chapter" : "chapters" }}; each has a checkpoint “{{ done.label }}” in its History.
      <template v-if="done.skipped.length">
        Changed since the preview, so left alone: {{ done.skipped.map((s) => s.title).join(", ") }}.
      </template>
      <button type="button" class="btn btn-sm" @click="undo">Undo</button>
    </div>
    <div v-if="undone" class="notice ok" role="status" data-testid="replace-undone">{{ undone }}</div>

    <template v-if="found">
      <div class="toolbar">
        <span class="muted" data-testid="replace-count">{{ total }} {{ total === 1 ? "hit" : "hits" }} in {{ found.length }} {{ found.length === 1 ? "chapter" : "chapters" }}</span>
        <button v-if="replacement && hitCount" type="button" class="btn btn-primary" :disabled="busy" data-testid="replace-button" @click="replace">{{ label }}</button>
        <button v-else-if="hitCount" type="button" class="btn btn-sm" :disabled="busy" data-testid="replace-button" @click="replace">{{ label }}…</button>
      </div>
      <template v-for="(c, i) in found" :key="c.id">
        <h2 v-if="projectBreak(i)" class="small muted">{{ c.project_name }}</h2>
        <section class="card replace-chapter" data-testid="replace-chapter">
          <div class="card-head">
            <label class="check">
              <input type="checkbox" :checked="(chosen.get(c.id)?.size ?? 0) > 0" :indeterminate.prop="(chosen.get(c.id)?.size ?? 0) > 0 && (chosen.get(c.id)?.size ?? 0) < c.hits.length" @change="toggleChapter(c)" />
              <strong>{{ c.title }}</strong>
              <span v-if="c.state === 'experiment'" class="pill accent">experiment</span>
            </label>
            <span class="muted small">{{ chosen.get(c.id)?.size ?? 0 }} of {{ c.hits.length }}</span>
          </div>
          <ul class="rows hits">
            <li v-for="h in c.hits" :key="h.start" data-testid="replace-hit">
              <input type="checkbox" :aria-label="`${h.before}${h.match}${h.after}`" :checked="chosen.get(c.id)?.has(h.start)" @change="toggleHit(c, h.start)" />
              <RouterLink class="grow snippet hit-line" :to="at(c, h.start)"
                >{{ h.before }}<template v-if="replacement"><del>{{ h.match }}</del><ins>{{ replacement }}</ins></template
                ><mark v-else>{{ h.match }}</mark>{{ h.after }}</RouterLink
              >
            </li>
          </ul>
        </section>
      </template>
      <p v-if="!found.length" class="empty">Not found.</p>
    </template>
    <UndoToast :label="toast" :undo="done ? undo : null" :ms="10000" @dismiss="toast = null" />
  </template>
</template>
