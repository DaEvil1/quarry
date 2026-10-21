<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get, post } from "../api";
import { passkeysSupported, promptError, runSignIn } from "../passkey";
import { useSession } from "../stores/session";

const route = useRoute();
const router = useRouter();
const session = useSession();

const supported = passkeysSupported();
const busy = ref(false);
const error = ref("");
const useCode = ref(false);
const code = ref("");

function next(): string {
  const n = route.query.next;
  // only paths inside the app; never an absolute URL handed in through the query string
  return typeof n === "string" && n.startsWith("/") && !n.startsWith("//") ? n : "/";
}

onMounted(async () => {
  try {
    if (await session.load()) {
      await router.replace(next());
      return;
    }
  } catch {
    error.value = "Quarry can't reach the server, and this device hasn't signed in before. Try again when you're online.";
    return;
  }
  const setup = await get<{ needed: boolean }>("/api/setup").catch(() => null);
  if (setup?.needed) await router.replace("/setup");
});

async function signIn() {
  error.value = "";
  busy.value = true;
  try {
    await runSignIn();
    await session.load();
    await router.replace(next());
  } catch (e) {
    error.value = promptError(e) ?? "";
  } finally {
    busy.value = false;
  }
}

async function recover() {
  error.value = "";
  busy.value = true;
  try {
    await post("/api/auth/recover", { code: code.value });
    await session.load();
    await router.replace({ name: "settings", query: { recovered: "1" } });
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="solo">
    <div class="card">
      <div class="brand"><img src="/favicon.svg" alt="" />Quarry</div>
      <h1>Sign in</h1>
      <template v-if="!useCode">
        <p class="muted">Use the passkey on this device, or on your phone.</p>
        <div v-if="!supported" class="notice warn">This browser cannot use passkeys. Use a recovery code instead.</div>
        <div v-if="error" class="notice error" role="alert">{{ error }}</div>
        <div class="actions">
          <button
            type="button"
            class="btn btn-primary"
            data-testid="sign-in"
            :disabled="busy || !supported"
            @click="signIn"
          >
            Sign in with a passkey
          </button>
          <button type="button" class="linkish small" @click="useCode = true">Lost your passkey?</button>
        </div>
      </template>
      <form v-else class="form" @submit.prevent="recover">
        <p class="muted">Each recovery code works once. After signing in, add a new passkey under Settings.</p>
        <div class="field">
          <label for="code">Recovery code</label>
          <input id="code" v-model="code" type="text" autocomplete="one-time-code" spellcheck="false" required />
        </div>
        <div v-if="error" class="notice error" role="alert">{{ error }}</div>
        <div class="actions">
          <button class="btn btn-primary" type="submit" :disabled="busy">Sign in</button>
          <button type="button" class="linkish small" @click="(useCode = false), (error = '')">Use a passkey</button>
        </div>
      </form>
    </div>
  </div>
</template>
