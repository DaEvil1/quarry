<script setup lang="ts">
import { computed, nextTick, ref } from "vue";

import type { TimeValue } from "../types";
import { numberOf, parseTime, timeText, type Unit } from "../world/when";

// When something is set (docs/SPEC.md §13.1.1): a time (a number, an optional end, a free label, "about"), not set,
// or outside time. Shown as text ("year 312", the label with the number small beside it, "outside time"); click to
// change it in place, Enter or Set saves, Esc cancels. `carried` is shown, muted, when it has no time of its own.
const props = withDefaults(defineProps<{ value: TimeValue; unit: Unit; label?: string; placeholder?: string; carried?: string; disabled?: boolean }>(), {
  label: "When",
  placeholder: "+ when",
  carried: "",
  disabled: false,
});
const emit = defineEmits<{ save: [value: TimeValue] }>();

const editing = ref(false);
const state = ref<"time" | "none" | "outside">("none");
const at = ref("");
const end = ref("");
const label = ref("");
const approx = ref(false);
const box = ref<HTMLInputElement | null>(null);
const text = computed(() => timeText(props.value, props.unit));
const small = computed(() => numberOf(props.value, props.unit));
const bad = computed(() => state.value === "time" && (parseTime(at.value) === null || (end.value.trim() !== "" && (parseTime(end.value) === null || parseTime(end.value)! < parseTime(at.value)!))));

async function start() {
  if (props.disabled) return;
  // a field with nothing set opens ready for a time (the usual reason to open it); "not set" is one click away
  state.value = props.value.outside_time ? "outside" : "time";
  at.value = props.value.time_at != null ? String(props.value.time_at) : "";
  end.value = props.value.time_end != null ? String(props.value.time_end) : "";
  label.value = props.value.time_label ?? "";
  approx.value = !!props.value.time_approx;
  editing.value = true;
  await nextTick();
  box.value?.focus();
}
function save() {
  if (bad.value) return;
  editing.value = false;
  if (state.value === "outside") emit("save", { time_at: null, time_end: null, time_label: null, time_approx: false, outside_time: true });
  else if (state.value === "none") emit("save", { time_at: null, time_end: null, time_label: null, time_approx: false, outside_time: false });
  else
    emit("save", {
      time_at: parseTime(at.value),
      time_end: end.value.trim() ? parseTime(end.value) : null,
      time_label: label.value.trim() || null,
      time_approx: approx.value,
      outside_time: false,
    });
}
function choose(s: "time" | "none" | "outside") {
  state.value = s;
  if (s === "time") void nextTick(() => box.value?.focus());
}
</script>

<template>
  <span v-if="!editing" class="time-field" :class="{ unset: !text, outside: props.value.outside_time }" data-testid="time-field">
    <button type="button" class="linkish small" :aria-label="`${props.label}: ${text || 'not set'}`" :disabled="props.disabled" @click="start">
      <template v-if="text">{{ text }}<span v-if="small" class="time-number">{{ small }}</span></template>
      <template v-else-if="props.carried"><span class="time-carried" :title="'Carries on from the chapter before it'">{{ props.carried }}</span></template>
      <template v-else>{{ props.placeholder }}</template>
    </button>
  </span>
  <form v-else class="time-form" data-testid="time-form" @submit.prevent="save" @keydown.esc.prevent.stop="editing = false">
    <span class="time-states" role="radiogroup" :aria-label="props.label">
      <label><input type="radio" :checked="state === 'time'" @change="choose('time')" /> a time</label>
      <label><input type="radio" :checked="state === 'none'" @change="choose('none')" /> not set</label>
      <label><input type="radio" :checked="state === 'outside'" @change="choose('outside')" /> outside time</label>
    </span>
    <template v-if="state === 'time'">
      <label class="small muted">{{ props.unit.unit }} <input ref="box" v-model="at" class="filter time-num" inputmode="decimal" aria-label="Time" placeholder="312" /></label>
      <label class="small muted">to <input v-model="end" class="filter time-num" inputmode="decimal" aria-label="Until (optional)" placeholder="" /></label>
      <label class="small check"><input v-model="approx" type="checkbox" aria-label="About" /> about</label>
      <input v-model="label" class="filter" aria-label="Label (optional)" placeholder="label, e.g. the winter of the long ice" maxlength="200" />
    </template>
    <button class="btn btn-sm btn-primary" type="submit" :disabled="bad">Set</button>
    <button class="btn btn-sm" type="button" @click="editing = false">Cancel</button>
  </form>
</template>
