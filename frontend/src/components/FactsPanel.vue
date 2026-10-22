<script setup lang="ts">
import { computed, ref } from "vue";

import { addFact, deleteFact, updateFact } from "../bible";
import type { Entity, Fact, Standing } from "../types";
import InlineText from "./InlineText.vue";

// An entry's facts: labelled values, added in one line, edited in place.
const props = defineProps<{
  world: string;
  entity: Entity;
  facts: Fact[];
  suggestions: string[];
  chapterTitles: Record<string, string>;
}>();
const emit = defineEmits<{ changed: []; error: [message: string] }>();

const label = ref("");
const value = ref("");
const STANDINGS: Standing[] = ["canon", "planned", "rumour"];
const unused = computed(() => props.suggestions.filter((s) => !props.facts.some((f) => f.label === s)));

async function run(fn: () => Promise<unknown>) {
  try {
    await fn();
    emit("changed");
  } catch (e) {
    emit("error", (e as Error).message);
  }
}

function add() {
  if (!label.value.trim()) return;
  const body = { label: label.value, value: value.value };
  label.value = value.value = "";
  void run(() => addFact(props.world, props.entity.id, body));
}

const set = (f: Fact, changes: Partial<Fact>) => run(() => updateFact(props.world, f, changes));
</script>

<template>
  <section class="card" data-testid="facts">
    <div class="card-head">
      <h2>Facts</h2>
      <span class="muted small">Anything worth keeping straight. Leave out what you don't know.</span>
    </div>
    <table v-if="props.facts.length" class="facts">
      <tbody>
        <tr v-for="f in props.facts" :key="f.id">
          <th><InlineText :value="f.label" label="Label" :maxlength="100" @save="(v) => v && set(f, { label: v })" /></th>
          <td class="grow">
            <InlineText :value="f.value" label="Value" placeholder="—" :maxlength="5000" @save="(v) => set(f, { value: v })" />
            <div class="evidence small muted">
              <InlineText
                :value="f.evidence ?? ''"
                label="Evidence"
                placeholder="+ where it says so"
                :maxlength="5000"
                @save="(v) => set(f, { evidence: v || null })"
              /><template v-if="f.evidence && f.established_in_chapter_id"> — {{ props.chapterTitles[f.established_in_chapter_id] ?? "a chapter" }}</template>
            </div>
          </td>
          <td>
            <select class="standing" :class="f.standing" :value="f.standing" aria-label="Standing" @change="set(f, { standing: ($event.target as HTMLSelectElement).value as Standing })">
              <option v-for="s in STANDINGS" :key="s" :value="s">{{ s }}</option>
            </select>
          </td>
          <td><button type="button" class="icon-btn small" :aria-label="`Remove ${f.label}`" @click="run(() => deleteFact(props.world, f.id))">×</button></td>
        </tr>
      </tbody>
    </table>
    <form class="actions fact-add" @submit.prevent="add">
      <input v-model="label" class="filter" list="fact-labels" placeholder="Label (e.g. eye colour)" aria-label="New fact label" maxlength="100" />
      <datalist id="fact-labels"><option v-for="s in unused" :key="s" :value="s" /></datalist>
      <input v-model="value" class="filter grow" placeholder="Value" aria-label="New fact value" maxlength="5000" />
      <button class="btn btn-sm" type="submit" :disabled="!label.trim()">Add</button>
    </form>
  </section>
</template>
