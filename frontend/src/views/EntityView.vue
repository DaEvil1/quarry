<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { deleteEntity, EntityConflict, fixes, getEntity, linkItem, sourceLink, updateEntity } from "../bible";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type EntityDetail, type EntityKind, type SourceRef } from "../types";
import NotFoundView from "./NotFoundView.vue";

const route = useRoute();
const router = useRouter();
const session = useSession();

const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const id = computed(() => String(route.params.id));
const detail = ref<EntityDetail | null>(null);
const missing = ref(false);
const error = ref("");
const notice = ref("");

const editing = ref(false);
const name = ref("");
const kind = ref<EntityKind>("character");
const body = ref("");
const aliases = ref<string[]>([]);
const newAlias = ref("");

const SOURCE_LABEL: Record<string, string> = { item: "Item", decision: "Decision", journal: "Journal", entity: "Bible" };
const projectName = (slug: string | null) =>
  slug ? (world.value?.projects.find((p) => p.slug === slug)?.name ?? slug) : "Whole world";

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

const groups = computed(() => {
  const out = new Map<string, NonNullable<typeof detail.value>["mentions"]>();
  for (const m of detail.value?.mentions ?? []) {
    const key = projectName(m.project);
    out.set(key, [...(out.get(key) ?? []), m]);
  }
  return [...out.entries()];
});

function startEdit() {
  const e = detail.value?.entity;
  if (!e) return;
  name.value = e.name;
  kind.value = e.kind;
  body.value = e.body;
  aliases.value = [...e.aliases];
  editing.value = true;
}

function addAlias() {
  const a = newAlias.value.trim();
  if (a && !aliases.value.includes(a)) aliases.value.push(a);
  newAlias.value = "";
}

async function save() {
  const e = detail.value?.entity;
  if (!e) return;
  error.value = "";
  try {
    await updateEntity(worldSlug.value, e, { name: name.value, kind: kind.value, body: body.value, aliases: aliases.value });
    editing.value = false;
    await load();
  } catch (err) {
    if (err instanceof EntityConflict) await load();
    error.value = (err as Error).message;
  }
}

async function remove() {
  const e = detail.value?.entity;
  if (!e || !confirm(`Remove "${e.name}" from the bible? Its tags on items go too; the texts stay as they are.`)) return;
  await deleteEntity(worldSlug.value, e.id);
  await router.push({ name: "bible", params: { world: worldSlug.value } });
}

async function act(fn: () => Promise<unknown>, done: string) {
  error.value = "";
  try {
    await fn();
    notice.value = done;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

// the three fixes, as plain functions for the template
const fixReplace = fixes.replace;
const fixSpelling = (world: string, token: string, entityId: string) => fixes.addSpelling(world, token, entityId);
const fixIgnore = fixes.notATypo;

const tag = (m: SourceRef) => act(() => linkItem(worldSlug.value, m.source_id, id.value), "Tagged.");
</script>

<template>
  <NotFoundView v-if="!world || missing" what="entry" />
  <template v-else-if="detail">
    <div class="page-head">
      <div>
        <div class="crumbs">
          <RouterLink :to="{ name: 'bible', params: { world: world.slug } }">Bible</RouterLink>
          · {{ ENTITY_KINDS.find((k) => k.value === detail!.entity.kind)?.label }}
        </div>
        <h1>{{ detail.entity.name }}</h1>
        <p v-if="detail.entity.aliases.length" class="muted">Also: {{ detail.entity.aliases.join(", ") }}</p>
      </div>
      <div class="actions">
        <button v-if="!editing" type="button" class="btn btn-sm" @click="startEdit">Edit</button>
        <button type="button" class="btn btn-sm" @click="remove">Remove</button>
      </div>
    </div>

    <div v-if="notice" class="notice ok" role="status">{{ notice }}</div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>

    <form v-if="editing" class="card form wide" @submit.prevent="save">
      <div class="actions">
        <div class="field grow">
          <label for="e-name">Name</label>
          <input id="e-name" v-model="name" type="text" maxlength="200" required />
        </div>
        <div class="field">
          <label for="e-kind">Kind</label>
          <select id="e-kind" v-model="kind">
            <option v-for="k in ENTITY_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label for="e-alias">Other spellings and names</label>
        <div class="chips">
          <span v-for="a in aliases" :key="a" class="chip static">
            {{ a }}
            <button type="button" class="chip-x" :aria-label="`Remove ${a}`" @click="aliases = aliases.filter((x) => x !== a)">×</button>
          </span>
        </div>
        <div class="actions">
          <input id="e-alias" v-model="newAlias" type="text" maxlength="200" @keydown.enter.prevent="addAlias" />
          <button type="button" class="btn btn-sm" @click="addAlias">Add</button>
        </div>
        <div class="hint">Mentions under these count for this entry, and they're never flagged as typos.</div>
      </div>
      <div class="field">
        <label for="e-body">Notes</label>
        <textarea id="e-body" v-model="body" class="capture-box" rows="10" />
      </div>
      <div class="actions">
        <button class="btn btn-primary" type="submit">Save</button>
        <button class="btn" type="button" @click="editing = false">Cancel</button>
      </div>
    </form>
    <section v-else-if="detail.entity.body" class="card">
      <p class="prose item-text">{{ detail.entity.body }}</p>
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
            <button type="button" class="btn btn-sm" @click="act(() => fixReplace(world!.slug, m.token, detail!.entity.id, { table: m.source_table, id: m.source_id }), 'Replaced.')">
              Replace
            </button>
            <button type="button" class="btn btn-sm" @click="act(() => fixSpelling(world!.slug, m.token, detail!.entity.id), 'Spelling added.')">
              Another spelling
            </button>
            <button type="button" class="btn btn-sm" @click="act(() => fixIgnore(world!.slug, m.token), 'Marked as not a typo.')">
              Not a typo
            </button>
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
              <!-- an item or decision is its own snippet; journal entries and bible pages have a title of their own -->
              <template v-if="m.source_table === 'journal' || m.source_table === 'entity'">
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
  </template>
</template>
