<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { get } from "../api";
import RecoveryCodes from "../components/RecoveryCodes.vue";
import { deviceLabel, passkeysSupported, promptError, runSetup } from "../passkey";
import { useSession } from "../stores/session";

const router = useRouter();
const session = useSession();

const ready = ref(false);
const enabled = ref(true);
const supported = passkeysSupported();
const token = ref("");
const name = ref("");
const label = ref(deviceLabel());
const busy = ref(false);
const error = ref("");
const codes = ref<string[] | null>(null);

onMounted(async () => {
  try {
    const status = await get<{ needed: boolean; enabled: boolean }>("/api/setup");
    if (!status.needed) {
      await router.replace("/login");
      return;
    }
    enabled.value = status.enabled;
  } catch (e) {
    error.value = (e as Error).message;
  }
  ready.value = true;
});

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    codes.value = await runSetup(token.value.trim(), name.value.trim(), label.value.trim());
  } catch (e) {
    error.value = promptError(e) ?? "";
  } finally {
    busy.value = false;
  }
}

async function finish() {
  await session.load();
  await router.replace({ name: "new-world" });
}
</script>

<template>
  <div class="solo">
    <div class="card">
      <div class="brand"><img src="/favicon.svg" alt="" />Quarry</div>
      <template v-if="codes">
        <h1>Save your recovery codes</h1>
        <RecoveryCodes :codes="codes" @done="finish" />
      </template>
      <template v-else-if="ready">
        <h1>Set up Quarry</h1>
        <p class="muted">
          You sign in with a passkey: your phone's or computer's own lock (fingerprint, face or PIN). No password to
          remember.
        </p>
        <div v-if="!supported" class="notice warn">This browser cannot use passkeys. Try a current Chrome, Edge, Safari or Firefox.</div>
        <div v-else-if="!enabled" class="notice warn">
          Setup is turned off. Set <code>QUARRY_SETUP_TOKEN</code> on the server and restart it.
        </div>
        <form v-else class="form" @submit.prevent="submit">
          <div class="field">
            <label for="token">Setup token</label>
            <input id="token" v-model="token" type="password" autocomplete="off" required />
            <div class="hint">The <code>QUARRY_SETUP_TOKEN</code> value from the server's settings.</div>
          </div>
          <div class="field">
            <label for="name">Your name</label>
            <input id="name" v-model="name" type="text" autocomplete="name" maxlength="100" required />
          </div>
          <div class="field">
            <label for="label">Name for this device's passkey</label>
            <input id="label" v-model="label" type="text" maxlength="100" required />
          </div>
          <div v-if="error" class="notice error" role="alert">{{ error }}</div>
          <div class="actions">
            <button class="btn btn-primary" type="submit" :disabled="busy">Create passkey</button>
          </div>
        </form>
      </template>
      <div v-if="error && !ready" class="notice error" role="alert">{{ error }}</div>
    </div>
  </div>
</template>
