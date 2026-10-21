<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{ codes: string[] }>();
const emit = defineEmits<{ done: [] }>();
const copied = ref(false);

async function copy() {
  try {
    await navigator.clipboard.writeText(props.codes.join("\n"));
    copied.value = true;
  } catch {
    copied.value = false;
  }
}

function download() {
  const text = `Quarry recovery codes\n\nEach code signs you in once, if you lose your passkeys.\n\n${props.codes.join("\n")}\n`;
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "quarry-recovery-codes.txt";
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div>
    <p>
      If you lose access to your passkeys, each of these codes signs you in once. Keep them somewhere safe, away from
      this device. They are not shown again.
    </p>
    <div class="codes" data-testid="recovery-codes">
      <span v-for="c in props.codes" :key="c">{{ c }}</span>
    </div>
    <div class="actions">
      <button type="button" class="btn btn-sm" @click="copy">{{ copied ? "Copied" : "Copy" }}</button>
      <button type="button" class="btn btn-sm" @click="download">Download</button>
      <span class="spacer" />
      <button type="button" class="btn btn-primary" data-testid="codes-saved" @click="emit('done')">
        I've saved them
      </button>
    </div>
  </div>
</template>
