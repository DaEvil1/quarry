<script setup lang="ts">
import { usePrefs } from "../prefs";
import { ENTITY_KINDS, type EntityKind } from "../types";

// How writing feels on this device: name colours, cards, how quiet the editor stays while typing, and the page.
const prefs = usePrefs();

function togglePlain(k: EntityKind, coloured: boolean) {
  prefs.set("plainKinds", coloured ? prefs.plainKinds.filter((x) => x !== k) : [...prefs.plainKinds, k]);
}
const num = (e: Event) => Number((e.target as HTMLInputElement).value);
const on = (e: Event) => (e.target as HTMLInputElement).checked;
</script>

<template>
  <section class="card form wide" data-testid="writing-settings">
    <div class="card-head">
      <h2>Writing</h2>
      <span class="muted small">On this device</span>
    </div>

    <h3 class="small muted">Names</h3>
    <label class="check"><input type="checkbox" :checked="prefs.colourNames" @change="prefs.set('colourNames', on($event))" /> Colour names by kind</label>
    <div v-if="prefs.colourNames" class="chips kind-toggles">
      <label v-for="k in ENTITY_KINDS" :key="k.value" class="chip static" :class="`k-${k.value}`">
        <input type="checkbox" :checked="!prefs.plainKinds.includes(k.value)" @change="togglePlain(k.value, on($event))" />
        <span class="kname">{{ k.plural }}</span>
      </label>
    </div>
    <label class="check"><input type="checkbox" :checked="prefs.underlines" @change="prefs.set('underlines', on($event))" /> Underline likely misspellings of names</label>

    <h3 class="small muted">Cards</h3>
    <label class="check"><input type="checkbox" :checked="prefs.cardsWithCtrl" @change="prefs.set('cardsWithCtrl', on($event))" /> In the editor, only show a name's card while Ctrl is held</label>
    <div class="field">
      <label for="card-delay">Rest on a name for <strong>{{ prefs.cardDelay }} ms</strong> before its card shows</label>
      <input id="card-delay" type="range" min="150" max="1500" step="50" :value="prefs.cardDelay" @input="prefs.set('cardDelay', num($event))" />
    </div>
    <div class="field">
      <label for="quiet">After a keystroke, nothing opens for <strong>{{ (prefs.quietMs / 1000).toFixed(1) }} s</strong></label>
      <input id="quiet" type="range" min="0" max="4000" step="250" :value="prefs.quietMs" @input="prefs.set('quietMs', num($event))" />
    </div>

    <h3 class="small muted">Page</h3>
    <div class="field">
      <label for="text-size">Text size <strong>{{ prefs.textSize }} px</strong></label>
      <input id="text-size" type="range" min="14" max="26" step="1" :value="prefs.textSize" @input="prefs.set('textSize', num($event))" />
    </div>
    <div class="field">
      <label for="line-width">Line width <strong>{{ prefs.lineWidth }} characters</strong></label>
      <input id="line-width" type="range" min="45" max="110" step="5" :value="prefs.lineWidth" @input="prefs.set('lineWidth', num($event))" />
    </div>
    <label class="check"><input type="checkbox" :checked="prefs.focusMode" @change="prefs.set('focusMode', on($event))" /> Focus mode: dim all but the current paragraph</label>
    <label class="check"><input type="checkbox" :checked="prefs.typewriter" @change="prefs.set('typewriter', on($event))" /> Typewriter scrolling: keep the line being written mid-screen</label>

    <div class="actions">
      <button type="button" class="btn btn-sm" @click="prefs.reset()">Back to defaults</button>
    </div>
  </section>
</template>
