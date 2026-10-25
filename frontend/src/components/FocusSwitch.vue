<script setup lang="ts">
import { ref } from "vue";

import { focusOf, setFocus, type Focus } from "../focus";
import { useSession } from "../stores/session";
import type { World } from "../types";

// Writing · Planning (docs/SPEC.md §14.9): what is up front in this world for this person. It takes effect at once,
// without leaving the page, and is kept on the server, so the phone and the desk agree.
const props = defineProps<{ world: World }>();
const session = useSession();
const error = ref("");

async function pick(f: Focus) {
  if (focusOf(props.world) === f) return;
  error.value = "";
  const before = props.world;
  // at once: the nav reorders before the server answers
  session.putWorld({ ...before, focus: f });
  try {
    session.putWorld(await setFocus(before.slug, f));
  } catch (e) {
    session.putWorld(before);
    error.value = (e as Error).message;
  }
}
</script>

<template>
  <span class="mode-switch focus-switch" role="group" aria-label="Focus" data-testid="focus-switch" :title="error || 'What is up front in this world for you'">
    <button type="button" :class="{ on: focusOf(props.world) === 'writing' }" :aria-pressed="focusOf(props.world) === 'writing'" @click.stop="pick('writing')">Writing</button>
    <button type="button" :class="{ on: focusOf(props.world) === 'planning' }" :aria-pressed="focusOf(props.world) === 'planning'" @click.stop="pick('planning')">Planning</button>
  </span>
</template>
