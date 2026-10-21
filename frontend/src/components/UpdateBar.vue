<script setup lang="ts">
import { useRegisterSW } from "virtual:pwa-register/vue";

// The installed app keeps the version it has until it is reloaded. When a new version has been downloaded, say so
// and let the person reload when it suits them (text being written is kept on the device either way).
const HOUR = 60 * 60_000;

const { needRefresh, updateServiceWorker } = useRegisterSW({
  immediate: true,
  onRegisteredSW(_url, registration) {
    // a tab left open for days still notices new versions
    if (registration) setInterval(() => void registration.update(), HOUR);
  },
});
</script>

<template>
  <div v-if="needRefresh" class="update-bar" role="status" data-testid="update-bar">
    <span>A new version of Quarry is ready.</span>
    <button type="button" class="btn btn-sm btn-primary" @click="updateServiceWorker()">Reload</button>
    <button type="button" class="linkish small" @click="needRefresh = false">Later</button>
  </div>
</template>
