<script setup lang="ts">
import { computed, ref } from "vue";

import { typeOptions } from "../bible";
import type { Check, PanelActions } from "../companion";
import { decisionDay, type Gap } from "../followups";
import { usePrefs } from "../prefs";
import { ENTITY_KINDS, type EntityKind, type RelationType } from "../types";
import { EDITORS, type EditorName, type Finding } from "../world/findings";

// The writing companion beside the editor (docs/WORLD-MODEL.md §7): the chapter's own panel (point of view, cast,
// actions: the default slot) and the five editors, each a tab of rule-based findings with one-click actions. In a
// journal entry (docs/SPEC.md §14.1.1) the first tab is the entry's, and there is no Continuity tab: the checks are
// about chapters on the clock.

const props = defineProps<{
  findings: Finding[];
  checks: Check[];
  items: { id: string; title: string | null; body: string; passage?: string | null }[];
  /** the gap lines: planned changes that follow a decision, tied to this written chapter (docs/SPEC.md §16.4) */
  gaps?: Gap[];
  note: string;
  backIn: { context: string; note: string } | null;
  drafting: boolean;
  /** the text changed since the findings were worked out (Drafting waits for a break) */
  stale: boolean;
  types: RelationType[];
  world: string;
  actions: PanelActions;
  /** a journal entry, not a chapter */
  journal?: boolean;
  /** Include planned on the Continuity tab (docs/SPEC.md §14.6) */
  planned?: boolean;
  /** the tab to open on (a link "into the chapter's Loose ends", docs/SPEC.md §16.5) */
  startTab?: EditorName;
}>();
const emit = defineEmits<{ dismissBack: []; tab: [tab: string]; planned: [on: boolean] }>();

const prefs = usePrefs();
const tab = ref<"chapter" | EditorName>(props.startTab ?? "chapter");
const editors = computed(() => EDITORS.filter((e) => prefs.editors[e.name].on && !(props.journal && e.name === "continuity")));
const byEditor = computed(() => {
  const out = Object.fromEntries(EDITORS.map((e) => [e.name, [] as Finding[]])) as Record<EditorName, Finding[]>;
  for (const f of props.findings) out[f.editor].push(f);
  return out;
});
const openGaps = computed(() => (props.gaps ?? []).filter((g) => !g.not_yet));
const laterGaps = computed(() => (props.gaps ?? []).filter((g) => g.not_yet));
// the selection, read when the pointer or focus comes to a gap line (not while typing): "…, with the selection"
const selected = ref("");
const peek = () => (selected.value = props.actions.selection?.() ?? "");
const count = (e: EditorName) =>
  e === "continuity" ? props.checks.filter((c) => !c.later).length : e === "looseEnds" ? byEditor.value.looseEnds.length + props.items.length + openGaps.value.length : byEditor.value[e].length;
function pick(t: "chapter" | EditorName) {
  tab.value = t;
  limit.value = PAGE;
  emit("tab", t);
}
// a long list is shown a page at a time (it is redrawn after every pause while Revising)
const PAGE = 40;
const limit = ref(PAGE);
const listed = computed(() => (tab.value === "connections" ? connections.value : tab.value === "chapter" || tab.value === "continuity" ? [] : byEditor.value[tab.value]));

// connections: strong and medium shown, weak folded away unless asked for
const showWeak = ref(false);
const connections = computed(() => byEditor.value.connections.filter((f) => f.strength !== "weak" || f.rule !== "unrecorded" || showWeak.value));
const weak = computed(() => byEditor.value.connections.filter((f) => f.rule === "unrecorded" && f.strength === "weak").length);
const recording = ref<string | null>(null);
const options = (f: Finding) => (f.a && f.b ? typeOptions(props.types, f.a.kind, f.b.kind) : []);

// a one-liner typed in place
const summaries = ref<Record<string, string>>({});
const noteDraft = ref(props.note);
const moreKinds = ref<string | null>(null);
const KINDS = ENTITY_KINDS;
const COMMON: EntityKind[] = ["character", "place", "faction", "object"];
const laterChecks = computed(() => props.checks.filter((c) => c.later));
const openChecks = computed(() => props.checks.filter((c) => !c.later));
</script>

<template>
  <aside class="chapter-side companion" data-testid="companion">
    <div v-if="props.backIn" class="back-in" data-testid="back-in">
      <button type="button" class="icon-btn small close" aria-label="Dismiss" @click="emit('dismissBack')">×</button>
      <div class="small muted">Last time you stopped at</div>
      <div class="small">“…{{ props.backIn.context }}…” <a href="#" @click.prevent="props.actions.goBack()">Go there</a></div>
      <div v-if="props.backIn.note" class="small back-note">Next: {{ props.backIn.note }}</div>
    </div>

    <nav class="companion-tabs" aria-label="Companion">
      <button type="button" :class="{ on: tab === 'chapter' }" @click="pick('chapter')">{{ props.journal ? "Entry" : "Chapter" }}</button>
      <button v-for="e in editors" :key="e.name" type="button" :class="{ on: tab === e.name }" :title="e.about" :data-testid="`tab-${e.name}`" @click="pick(e.name)">
        {{ e.label }}<span v-if="count(e.name)" class="badge dim">{{ count(e.name) }}</span>
      </button>
    </nav>

    <div v-if="tab !== 'chapter' && props.drafting && props.stale" class="small muted drafting-note">
      Drafting: new findings wait for a break (a line of *** or opening a tab).
      <a href="#" @click.prevent="props.actions.update()">Update now</a>
    </div>

    <slot v-if="tab === 'chapter'" />

    <!-- Continuity: the checks over recorded data -->
    <section v-else-if="tab === 'continuity'" class="findings" data-testid="findings-continuity">
      <label class="toggle small" title="Planned facts and relationships count too; rumour never does">
        <input type="checkbox" :checked="props.planned" data-testid="include-planned" @change="emit('planned', ($event.target as HTMLInputElement).checked)" /> Include planned
      </label>
      <p v-if="!openChecks.length" class="muted small">Nothing to check in this chapter.</p>
      <div v-for="c in openChecks" :key="c.rule + c.key" class="finding">
        <div class="small">{{ c.message }}<span v-if="c.planned" class="pill" data-testid="planned-tag"> planned</span><template v-if="c.decided"> · <RouterLink :to="{ name: 'decisions', params: { world: props.world }, hash: `#d-${c.decided.id}` }" :title="c.decided.text" data-testid="finding-decided">decided {{ decisionDay(c.decided.decided_on) }}</RouterLink></template></div>
        <div class="qrow">
          <button v-for="e in c.entities" :key="e.id" type="button" class="qchip" :class="`k-${e.kind}`" @click="props.actions.open(e)">{{ e.name }}</button>
          <button v-if="c.rule === 'fact_conflict' && c.label && c.kind" type="button" class="qchip" title="The label holds several values at once for this kind" @click="props.actions.several(c.kind, c.label)">Both are true (several values)</button>
          <button v-if="c.rule === 'role_clash' && c.end && c.before" type="button" class="qchip" @click="props.actions.endBefore(c.end.id, c.before.id)">End {{ c.end.name }}'s before {{ c.before.name }}'s</button>
          <button type="button" class="qchip quiet" title="Planted on purpose: never flag it again" @click="props.actions.resolve(c.rule, c.key, 'intentional')">Intentional</button>
          <button type="button" class="qchip quiet" @click="props.actions.resolve(c.rule, c.key, 'later')">Later</button>
        </div>
      </div>
      <details v-if="laterChecks.length" class="small">
        <summary>{{ laterChecks.length }} kept for later</summary>
        <div v-for="c in laterChecks" :key="c.rule + c.key" class="finding later">{{ c.message }}</div>
      </details>
      <RouterLink class="small" :to="{ name: 'checks', params: { world: props.world } }">All checks in the world</RouterLink>
    </section>

    <!-- the editors with findings in the text -->
    <section v-else class="findings" :data-testid="`findings-${tab}`">
      <template v-if="tab === 'looseEnds'">
        <label class="small muted" for="next-note">A note for next time</label>
        <textarea id="next-note" v-model="noteDraft" class="capture-box note-box" rows="2" placeholder="What's next?" @blur="noteDraft !== props.note && props.actions.saveNote(noteDraft)" />
        <div v-if="props.items.length" class="small muted">Tied to this {{ props.journal ? "entry" : "chapter" }}</div>
        <div
          v-for="i in props.items"
          :key="i.id"
          class="finding"
          data-testid="loose-item"
          @mouseenter="i.passage && props.actions.showPassage?.(i.passage)"
          @mouseleave="i.passage && props.actions.showPassage?.(null)"
        >
          <RouterLink class="small" :to="{ name: 'item', params: { world: props.world, id: i.id } }">{{ i.title || i.body.split("\n")[0] }}</RouterLink>
          <blockquote v-if="i.passage" class="small muted passage-quote">{{ i.passage }}</blockquote>
        </div>
        <template v-if="props.gaps?.length">
          <div class="small muted">Decided, not in the book yet</div>
          <div v-for="g in openGaps" :key="g.key" class="finding gap-line" data-testid="gap-line" @pointerenter="peek" @focusin="peek">
            <div class="small">Decided {{ decisionDay(g.decision.decided_on) }}: {{ g.what }} · not in the book yet</div>
            <RouterLink class="small muted gap-quote" :to="{ name: 'decisions', params: { world: props.world }, hash: `#d-${g.decision.id}` }">“{{ g.decision.text }}”</RouterLink>
            <div class="qrow">
              <button type="button" class="qchip primary" data-testid="gap-canon" @mousedown.prevent="peek" @click="props.actions.canonHere?.(g, selected || null)">{{ selected ? "Make it canon here, with the selection" : "Make it canon here" }}</button>
              <button type="button" class="qchip quiet" data-testid="gap-not-yet" @click="props.actions.notYet?.(g)">Not yet</button>
            </div>
          </div>
          <details v-if="laterGaps.length" class="small" data-testid="gap-later">
            <summary>Not yet · {{ laterGaps.length }}</summary>
            <div v-for="g in laterGaps" :key="g.key" class="finding later">
              Decided {{ decisionDay(g.decision.decided_on) }}: {{ g.what }}
              <button type="button" class="linkish small" data-testid="gap-show-again" @click="props.actions.showAgain?.(g)">Show again</button>
            </div>
          </details>
        </template>
        <button type="button" class="btn btn-sm stash-btn" @click="props.actions.stash()">Stash a thought <kbd>Ctrl Shift S</kbd></button>
      </template>

      <p v-if="!listed.length && tab !== 'looseEnds'" class="muted small">Nothing here.</p>
      <div
        v-for="f in listed.slice(0, limit)"
        :key="f.rule + f.key"
        class="finding"
        :class="[f.rule, f.strength]"
        :data-rule="f.rule"
      >
        <div class="small">
          <span v-if="f.strength" class="strength" :title="`${f.strength}: ${f.strength === 'strong' ? 'same sentence' : f.strength === 'medium' ? 'same paragraph' : 'same chapter'}`">{{ f.strength === "strong" ? "●" : f.strength === "medium" ? "◐" : "○" }}</span>
          {{ f.message }}
        </div>
        <div class="qrow">
          <button v-if="f.fix" type="button" class="qchip primary" @click="props.actions.fix(f)">{{ f.fix.label }}</button>

          <template v-if="f.rule === 'unrecorded'">
            <template v-if="recording === f.key">
              <button v-for="o in options(f)" :key="`${o.type.id}|${o.forward}`" type="button" class="qchip" @click="props.actions.link(f.a!, f.b!, o.type.id, o.forward), (recording = null)">{{ o.reads }}</button>
              <button type="button" class="qchip quiet" @click="recording = null">Cancel</button>
            </template>
            <template v-else>
              <button type="button" class="qchip" @click="recording = f.key">Record how…</button>
              <button type="button" class="qchip quiet" @click="props.actions.resolve(f.rule, f.key, 'not_connected')">Not connected</button>
            </template>
          </template>

          <template v-if="f.rule === 'where'">
            <button v-for="p in f.places" :key="p.id" type="button" class="qchip k-place" @click="props.actions.isAt(f.a!, p)">at {{ p.name }}</button>
          </template>

          <template v-if="f.rule === 'new_name'">
            <button v-for="k in moreKinds === f.key ? KINDS.map((x) => x.value) : COMMON" :key="k" type="button" class="qchip" :class="`k-${k}`" @click="props.actions.create(f.word!, k)">+ {{ KINDS.find((x) => x.value === k)?.label }}</button>
            <button v-if="moreKinds !== f.key" type="button" class="qchip quiet" @click="moreKinds = f.key">More…</button>
            <button type="button" class="qchip quiet" @click="props.actions.notAName(f.word!)">Not a name</button>
          </template>

          <template v-if="f.rule === 'near_miss' || f.rule === 'other_name'">
            <button type="button" class="qchip" @click="props.actions.addSpelling(f.a!, f.word!)">Another spelling</button>
            <button type="button" class="qchip quiet" @click="props.actions.notAName(f.word!)">Not a typo</button>
          </template>

          <template v-if="f.rule === 'crossover'">
            <button type="button" class="qchip primary" @click="props.actions.share(f.a!)">Share with the world</button>
            <button type="button" class="qchip quiet" title="Leave it in its book's bible; not flagged again for this book" @click="props.actions.resolve(f.rule, f.key, 'intentional')">Intentional</button>
          </template>

          <template v-if="f.rule === 'evidence_retired' && f.evidence">
            <button v-for="c in f.evidence.found.slice(0, 2)" :key="c.id" type="button" class="qchip primary" @click="props.actions.reAnchor(f, c.id)">Re-anchor to {{ c.title }}</button>
            <button v-if="f.a" type="button" class="qchip" @click="props.actions.open(f.a)">Re-anchor…</button>
            <button type="button" class="qchip quiet" @click="props.actions.resolve(f.rule, f.key, 'intentional')">Dismiss</button>
          </template>

          <template v-if="f.rule === 'missing_label'">
            <button type="button" class="qchip primary" @click="props.actions.addLabel(f.a!, f.label!)">Add it</button>
            <button type="button" class="qchip quiet" @click="props.actions.resolve(f.rule, f.key, 'intentional')">Not for this one</button>
          </template>

          <template v-if="f.rule === 'no_summary'">
            <input v-model="summaries[f.key]" class="qinput" :placeholder="`${f.a!.name} in one line`" :aria-label="`One line about ${f.a!.name}`" maxlength="300" @keydown.enter.prevent="summaries[f.key] && props.actions.summary(f.a!, summaries[f.key]!)" />
          </template>

          <button v-if="(f.rule === 'tk' || f.rule === 'unsure') && props.actions.question" type="button" class="qchip" @click="props.actions.question(f)">Make a question</button>
          <button v-if="['echo', 'long_sentence', 'doubled', 'where'].includes(f.rule)" type="button" class="qchip quiet" @click="props.actions.resolve(f.rule, f.key, 'intentional')">Leave it</button>
          <button v-if="f.from !== undefined" type="button" class="qchip quiet" @click="props.actions.jump(f)">Go</button>
        </div>
      </div>
      <button v-if="listed.length > limit" type="button" class="linkish small" @click="limit += PAGE">Show {{ Math.min(PAGE, listed.length - limit) }} more of {{ listed.length - limit }}</button>
      <button v-if="tab === 'connections' && weak" type="button" class="linkish small" @click="showWeak = !showWeak">
        {{ showWeak ? "Hide" : "Show" }} {{ weak }} weak (only in the same chapter)
      </button>
    </section>
  </aside>
</template>
