<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { listLabels, renameLabel, renameRole, renameValue, setLabelSwitches, setRoleSwitch, undoRename, undoRoleRename, type Renamed } from "../bible";
import { resolutions, resolve, unresolve, type Resolution } from "../companion";
import UndoToast from "../components/UndoToast.vue";
import { useSession } from "../stores/session";
import { ENTITY_KINDS, type EntityKind } from "../types";
import { useCards, type LabelsPage } from "../world/cards";
import { missingKey, norm } from "../world/labels";
import NotFoundView from "./NotFoundView.vue";

// The world's fact labels, per kind (docs/SPEC.md §12.6.3): how many entries have each, its values and who has them;
// renaming and merging labels and values across the world, with Undo; and the per-label switches: several values,
// expected on every entry. Labels and values come from the facts; nothing here is a fixed list.
const route = useRoute();
const session = useSession();
const cards = useCards();
const worldSlug = computed(() => String(route.params.world));
const world = computed(() => session.world(worldSlug.value));
const page = ref<LabelsPage | null>(null);
const resolved = ref<Resolution[]>([]);
const error = ref("");
const open = ref<string | null>(typeof route.hash === "string" && route.hash ? decodeURIComponent(route.hash.slice(1)) : null);

async function load() {
  if (!world.value) return;
  error.value = "";
  try {
    [page.value, resolved.value] = await Promise.all([listLabels(worldSlug.value), resolutions(worldSlug.value)]);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
watch(worldSlug, load, { immediate: true });
watch(worldSlug, (w) => void cards.load(w), { immediate: true });

const plural = (k: string) => ENTITY_KINDS.find((x) => x.value === k)?.plural ?? k;
const anchor = (kind: string, label: string) => `${kind}:${norm(label)}`;
const kinds = computed(() => (page.value?.kinds ?? []).filter((k) => k.labels.length));
/** The same label on other kinds: its own row there. */
const elsewhere = (kind: string, label: string) =>
  kinds.value.filter((k) => k.kind !== kind).flatMap((k) => k.labels.filter((l) => norm(l.label) === norm(label)).map((l) => ({ kind: k.kind, count: l.count, label: l.label })));
/** Most entries of the kind have it, but it isn't expected: pointed out, never marked by itself. */
const candidate = (count: number, total: number, expected: boolean) => !expected && total >= 4 && count < total && count / total >= 0.75;

async function run(fn: () => Promise<unknown>) {
  error.value = "";
  try {
    await fn();
    await load();
    void cards.refresh(worldSlug.value);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
const toggle = (kind: EntityKind, label: string, field: "several" | "expected", on: boolean) => run(() => setLabelSwitches(worldSlug.value, kind, label, { [field]: on }));

// rename or merge, with one step back
const toast = ref<{ label: string; undo: () => Promise<{ restored: number; skipped: number }> } | null>(null);
const labelDraft = ref<Record<string, string>>({});
const everywhere = ref<Record<string, boolean>>({});
const valueDraft = ref<Record<string, string>>({});
function renamed(done: Renamed) {
  toast.value = { label: done.message, undo: () => undoRename(worldSlug.value, done) };
}
const doRenameLabel = (kind: EntityKind, label: string) => {
  const key = anchor(kind, label);
  const to = (labelDraft.value[key] ?? "").trim();
  if (!to || to === label) return;
  void run(async () => {
    const done = await renameLabel(worldSlug.value, { kind, old: label, new: to, everywhere: !!everywhere.value[key] });
    labelDraft.value[key] = "";
    open.value = anchor(kind, to);
    renamed(done);
  });
};
const doRenameValue = (kind: EntityKind, label: string, value: string) => {
  const key = `${anchor(kind, label)}|${norm(value)}`;
  const to = (valueDraft.value[key] ?? "").trim();
  if (!to || to === value) return;
  void run(async () => {
    renamed(await renameValue(worldSlug.value, { kind, label, old: value, new: to }));
    valueDraft.value[key] = "";
  });
};
async function undo() {
  const t = toast.value;
  if (!t) return;
  const r = await t.undo();
  toast.value = null;
  await load();
  void cards.refresh(worldSlug.value);
  if (r.skipped) error.value = `${r.skipped} change${r.skipped === 1 ? "" : "s"} changed since, and kept the new spelling.`;
}

// roles in groups (docs/SPEC.md §13.4): rename or merge across the world, and "one at a time"
const roles = computed(() => page.value?.roles ?? []);
const roleDraft = ref<Record<string, string>>({});
const doRenameRole = (role: string) => {
  const to = (roleDraft.value[norm(role)] ?? "").trim();
  if (!to || to === role) return;
  void run(async () => {
    const done = await renameRole(worldSlug.value, role, to);
    roleDraft.value[norm(role)] = "";
    toast.value = { label: done.message, undo: () => undoRoleRename(worldSlug.value, done) };
  });
};
const toggleRole = (role: string, on: boolean) => run(() => setRoleSwitch(worldSlug.value, role, on));

// an expected label's missing entries: "Not for this one", or back to asking
const resolution = (entityId: string, label: string) => resolved.value.find((r) => r.rule === "missing_label" && r.key === missingKey(entityId, label));
const notForThisOne = (entityId: string, label: string) => run(() => resolve(worldSlug.value, "missing_label", missingKey(entityId, label), "intentional"));
const askAgain = (r: Resolution) => run(() => unresolve(worldSlug.value, r.id));
</script>

<template>
  <NotFoundView v-if="!world" what="world" />
  <template v-else>
    <div class="page-head">
      <div>
        <div class="crumbs"><RouterLink :to="{ name: 'bible', params: { world: world.slug } }">Bible</RouterLink></div>
        <h1>Labels</h1>
        <p class="muted">
          The labels your facts use, per kind, with their values. Rename or merge them to keep spellings the same; mark a
          label as holding several values, or as expected on every entry of its kind.
        </p>
      </div>
      <div class="actions">
        <RouterLink class="btn btn-sm" :to="{ name: 'relation-types', params: { world: world.slug } }">Kinds of relationship</RouterLink>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <p v-if="page && !kinds.length && !roles.length" class="empty">No facts yet. Labels show up here once entries have facts.</p>

    <section v-for="k in kinds" :key="k.kind" class="card labels-kind" :class="`k-${k.kind}`" :data-testid="`labels-${k.kind}`">
      <h2><span class="kdot" /> {{ plural(k.kind) }} <span class="muted small">({{ k.total }})</span></h2>
      <details
        v-for="l in k.labels"
        :id="anchor(k.kind, l.label)"
        :key="l.label"
        class="label-row"
        :open="open === anchor(k.kind, l.label)"
        :data-label="l.label"
        @toggle="($event.target as HTMLDetailsElement).open ? (open = anchor(k.kind, l.label)) : open === anchor(k.kind, l.label) && (open = null)"
      >
        <summary>
          <strong>{{ l.label }}</strong>: <span data-testid="label-count">{{ l.count }} of {{ k.total }} {{ plural(k.kind).toLowerCase() }}</span>
          <span v-if="l.values.length" class="muted small"> · {{ l.values.slice(0, 4).map((v) => `${v.value} ${v.count}`).join(" · ") }}{{ l.values.length > 4 ? " · …" : "" }}</span>
          <span v-if="l.several" class="pill accent">several values</span>
          <span v-if="l.expected" class="pill warn">expected</span>
          <span v-if="candidate(l.count, k.total, l.expected)" class="pill" data-testid="candidate">{{ l.count }} of {{ k.total }} have it</span>
        </summary>
        <div class="label-body">
          <p v-for="o in elsewhere(k.kind, l.label)" :key="o.kind" class="small muted">
            also used for <a :href="`#${anchor(o.kind, o.label)}`" @click="open = anchor(o.kind, o.label)">{{ plural(o.kind).toLowerCase() }} ({{ o.count }})</a>
          </p>
          <div class="switches">
            <label class="check"><input type="checkbox" :checked="l.several" data-testid="switch-several" @change="toggle(k.kind, l.label, 'several', ($event.target as HTMLInputElement).checked)" /> Several values at once (eye colour green and red; languages)</label>
            <label class="check"><input type="checkbox" :checked="l.expected" data-testid="switch-expected" @change="toggle(k.kind, l.label, 'expected', ($event.target as HTMLInputElement).checked)" /> Expected on every {{ ENTITY_KINDS.find((x) => x.value === k.kind)?.label.toLowerCase() }}</label>
          </div>
          <form class="actions rename" @submit.prevent="doRenameLabel(k.kind, l.label)">
            <label class="small muted" :for="`rl-${anchor(k.kind, l.label)}`">Rename or merge into</label>
            <input :id="`rl-${anchor(k.kind, l.label)}`" v-model="labelDraft[anchor(k.kind, l.label)]" class="filter" :list="`labels-${k.kind}`" maxlength="100" :placeholder="l.label" :aria-label="`Rename ${l.label}`" />
            <label v-if="elsewhere(k.kind, l.label).length" class="small check"><input v-model="everywhere[anchor(k.kind, l.label)]" type="checkbox" /> for every kind</label>
            <button class="btn btn-sm" type="submit">Rename</button>
          </form>
          <ul class="rows label-values">
            <li v-for="v in l.values" :key="v.value" :data-value="v.value">
              <span class="value-name"><strong>{{ v.value }}</strong> <span class="muted">{{ v.count }}</span></span>
              <span class="grow small">
                <template v-for="(e, i) in v.entries" :key="e.id"><span v-if="i">, </span><RouterLink class="kname" :class="`k-${e.kind}`" :to="{ name: 'entity', params: { world: world.slug, id: e.id } }">{{ e.name }}</RouterLink></template>
              </span>
              <form class="actions" @submit.prevent="doRenameValue(k.kind, l.label, v.value)">
                <input v-model="valueDraft[`${anchor(k.kind, l.label)}|${norm(v.value)}`]" class="filter small-input" :list="`values-${anchor(k.kind, l.label)}`" maxlength="5000" :placeholder="`${v.value} → …`" :aria-label="`Rename or merge ${v.value}`" />
                <button class="btn btn-sm" type="submit">Rename</button>
              </form>
            </li>
          </ul>
          <datalist :id="`values-${anchor(k.kind, l.label)}`"><option v-for="v in l.values" :key="v.value" :value="v.value" /></datalist>
          <template v-if="l.expected && l.without.length">
            <h3 class="small muted">Without it</h3>
            <ul class="rows" data-testid="without">
              <li v-for="e in l.without" :key="e.id" :class="{ dim: e.resolved }">
                <RouterLink class="kname grow" :class="`k-${e.kind}`" :to="{ name: 'entity', params: { world: world.slug, id: e.id }, query: { add: l.label } }">{{ e.name }}</RouterLink>
                <template v-if="resolution(e.id, l.label)">
                  <span class="muted small">not for this one</span>
                  <button type="button" class="qchip quiet" @click="askAgain(resolution(e.id, l.label)!)">Ask again</button>
                </template>
                <template v-else>
                  <RouterLink class="qchip" :to="{ name: 'entity', params: { world: world.slug, id: e.id }, query: { add: l.label } }">Add it</RouterLink>
                  <button type="button" class="qchip quiet" @click="notForThisOne(e.id, l.label)">Not for this one</button>
                </template>
              </li>
            </ul>
          </template>
        </div>
      </details>
      <datalist :id="`labels-${k.kind}`"><option v-for="l in k.labels" :key="l.label" :value="l.label" /></datalist>
    </section>
    <section v-if="roles.length" class="card labels-kind" data-testid="labels-roles">
      <h2>Roles <span class="muted small">({{ roles.length }})</span></h2>
      <p class="muted small">Roles in groups, from relationships whose kind has a role (member of, leads …). A role marked one at a time is a Continuity finding when two hold it in the same group at once.</p>
      <details v-for="r in roles" :key="r.role" class="label-row" :data-role="r.role">
        <summary>
          <strong>{{ r.role }}</strong>: <span>{{ r.count }} relationship{{ r.count === 1 ? "" : "s" }}</span>
          <span v-if="r.types.length" class="muted small"> · {{ r.types.join(", ") }}</span>
          <span v-if="r.one_at_a_time" class="pill warn">one at a time</span>
        </summary>
        <div class="label-body">
          <div class="switches">
            <label class="check"><input type="checkbox" :checked="r.one_at_a_time" data-testid="switch-one-at-a-time" @change="toggleRole(r.role, ($event.target as HTMLInputElement).checked)" /> One at a time (only one {{ r.role }} in a group at once)</label>
          </div>
          <form class="actions rename" @submit.prevent="doRenameRole(r.role)">
            <label class="small muted" :for="`rr-${norm(r.role)}`">Rename or merge into</label>
            <input :id="`rr-${norm(r.role)}`" v-model="roleDraft[norm(r.role)]" class="filter" list="roles-all" maxlength="100" :placeholder="r.role" :aria-label="`Rename ${r.role}`" />
            <button class="btn btn-sm" type="submit">Rename</button>
          </form>
          <p v-if="r.groups.length" class="small">
            <span class="muted">In </span>
            <template v-for="(g, i) in r.groups" :key="g.id"><span v-if="i">, </span><RouterLink class="kname" :class="`k-${g.kind}`" :to="{ name: 'entity', params: { world: world.slug, id: g.id } }">{{ g.name }}</RouterLink></template>
          </p>
        </div>
      </details>
      <datalist id="roles-all"><option v-for="r in roles" :key="r.role" :value="r.role" /></datalist>
    </section>
    <UndoToast :label="toast?.label ?? null" :undo="undo" :ms="15000" @dismiss="toast = null" />
  </template>
</template>
