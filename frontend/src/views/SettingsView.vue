<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { del, get, patch, post } from "../api";
import RecoveryCodes from "../components/RecoveryCodes.vue";
import WritingSettings from "../components/WritingSettings.vue";
import { deviceLabel, passkeysSupported, promptError, runAddPasskey } from "../passkey";
import { readLastUsed } from "../lastUsed";
import { clearOfflineCopy, keepPictures, lastSynced, localPictures, localSummary, persistStorage, storageInfo, syncWorld } from "../offline";
import { sizeText } from "../pictures";
import { useSession } from "../stores/session";
import type { PasskeyInfo, User } from "../types";

const route = useRoute();
const router = useRouter();
const session = useSession();
const recovered = route.query.recovered === "1";
const supported = passkeysSupported();

const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });
const day = (iso: string | null) => (iso ? fmt.format(new Date(iso)) : "never");

// profile
const displayName = ref(session.user?.display_name ?? "");
const profileMsg = ref("");
const profileError = ref("");

async function saveProfile() {
  profileMsg.value = profileError.value = "";
  try {
    const u = await patch<User>("/api/me", { display_name: displayName.value });
    if (session.me) session.me.user = u;
    displayName.value = u.display_name;
    profileMsg.value = "Saved.";
  } catch (e) {
    profileError.value = (e as Error).message;
  }
}

// passkeys
const passkeys = ref<PasskeyInfo[]>([]);
const newLabel = ref(deviceLabel());
const keyError = ref("");
const keyBusy = ref(false);
const renaming = ref<string | null>(null);
const renameTo = ref("");

async function loadKeys() {
  passkeys.value = await get<PasskeyInfo[]>("/api/auth/passkeys");
}

async function addKey() {
  keyError.value = "";
  keyBusy.value = true;
  try {
    await runAddPasskey(newLabel.value.trim() || "Passkey");
    await loadKeys();
  } catch (e) {
    keyError.value = promptError(e) ?? "";
  } finally {
    keyBusy.value = false;
  }
}

function startRename(k: PasskeyInfo) {
  renaming.value = k.id;
  renameTo.value = k.label;
}

async function saveRename(k: PasskeyInfo) {
  keyError.value = "";
  try {
    await patch(`/api/auth/passkeys/${k.id}`, { label: renameTo.value });
    renaming.value = null;
    await loadKeys();
  } catch (e) {
    keyError.value = (e as Error).message;
  }
}

async function removeKey(k: PasskeyInfo) {
  if (!confirm(`Remove the passkey "${k.label}"? That device can no longer sign in.`)) return;
  keyError.value = "";
  try {
    await del(`/api/auth/passkeys/${k.id}`);
    await loadKeys();
  } catch (e) {
    keyError.value = (e as Error).message;
  }
}

// recovery codes
const codesLeft = ref<number | null>(null);
const newCodes = ref<string[] | null>(null);

async function loadCodes() {
  codesLeft.value = (await get<{ left: number }>("/api/auth/recovery-codes")).left;
}

async function regenerate() {
  if (!confirm("Make a new set of recovery codes? The old codes stop working.")) return;
  newCodes.value = (await post<{ recovery_codes: string[] }>("/api/auth/recovery-codes")).recovery_codes;
}

async function codesSaved() {
  newCodes.value = null;
  await loadCodes();
}

async function signOut() {
  await session.signOut();
  await router.push("/login");
}

// the offline copy of the world last opened on this device
const offlineWorld = session.world(readLastUsed().world ?? "") ?? session.worlds[0];
const offline = ref<{ synced: string | null; chapters: number; revisions: number; persisted: boolean; usage: number | null; pictures: { count: number; bytes: number } } | null>(null);
const offlineMsg = ref("");

async function loadOffline() {
  if (!offlineWorld) return;
  const [synced, summary, storage, pictures] = await Promise.all([lastSynced(offlineWorld.slug), localSummary(offlineWorld.slug), storageInfo(), localPictures(offlineWorld.slug)]);
  offline.value = { synced, ...summary, ...storage, pictures };
}

async function syncNow() {
  if (!offlineWorld) return;
  offlineMsg.value = (await syncWorld(offlineWorld.slug)) ? "Synced." : "Offline: try again when connected.";
  await persistStorage();
  await loadOffline();
  await keepPictures(offlineWorld.slug);
  await loadOffline();
}

async function clearCopy() {
  if (!confirm("Remove the offline copy from this device? Text not yet saved stays; the copy is fetched again when you sync.")) return;
  await clearOfflineCopy();
  offlineMsg.value = "Removed.";
  await loadOffline();
}

const mb = (bytes: number | null) => (bytes === null ? "unknown" : `${(bytes / 1024 / 1024).toFixed(1)} MB`);
const when = (iso: string | null) => (iso ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso)) : "never");

onMounted(() => Promise.all([loadKeys(), loadCodes(), loadOffline()]));
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Settings</h1>
      <p class="muted">New to something here? <RouterLink :to="{ name: 'guide' }" data-testid="settings-guide">The Guide</RouterLink> walks through it.</p>
    </div>
    <button type="button" class="btn btn-sm" @click="signOut">Sign out</button>
  </div>

  <div v-if="recovered" class="notice accent">
    You signed in with a recovery code. Add a passkey for this device below, so you don't use up your codes.
  </div>

  <form class="card form" @submit.prevent="saveProfile">
    <h2>Profile</h2>
    <div class="field">
      <label for="display-name">Your name</label>
      <input id="display-name" v-model="displayName" type="text" maxlength="100" required />
    </div>
    <div v-if="profileError" class="notice error" role="alert">{{ profileError }}</div>
    <div class="actions">
      <button class="btn btn-primary" type="submit">Save</button>
      <span v-if="profileMsg" class="muted small">{{ profileMsg }}</span>
    </div>
  </form>

  <WritingSettings />

  <section class="card">
    <div class="card-head">
      <h2>Passkeys</h2>
      <span class="muted small">Each device you sign in from has its own.</span>
    </div>
    <ul class="rows" data-testid="passkey-list">
      <li v-for="k in passkeys" :key="k.id">
        <template v-if="renaming === k.id">
          <form class="actions grow" @submit.prevent="saveRename(k)">
            <div class="field grow">
              <label :for="`rename-${k.id}`" class="visually-hidden">New name</label>
              <input :id="`rename-${k.id}`" v-model="renameTo" type="text" maxlength="100" required />
            </div>
            <button class="btn btn-sm btn-primary" type="submit">Save</button>
            <button class="btn btn-sm" type="button" @click="renaming = null">Cancel</button>
          </form>
        </template>
        <template v-else>
          <div class="grow">
            <div>{{ k.label }}</div>
            <div class="muted small">Added {{ day(k.created_at) }} · last used {{ day(k.last_used_at) }}</div>
          </div>
          <button type="button" class="btn btn-sm" @click="startRename(k)">Rename</button>
          <button type="button" class="btn btn-sm" :disabled="passkeys.length === 1" @click="removeKey(k)">
            Remove
          </button>
        </template>
      </li>
    </ul>
    <form v-if="supported" class="form" @submit.prevent="addKey">
      <div class="field">
        <label for="new-key">Add a passkey for this device</label>
        <input id="new-key" v-model="newLabel" type="text" maxlength="100" required />
        <div class="hint">To add your phone, open Quarry on the phone, sign in, and add it there.</div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" type="submit" :disabled="keyBusy">Add passkey</button>
      </div>
    </form>
    <div v-if="keyError" class="notice error" role="alert">{{ keyError }}</div>
  </section>

  <section v-if="offlineWorld" class="card" data-testid="offline-settings">
    <div class="card-head">
      <h2>Offline copy</h2>
      <span class="muted small">{{ offlineWorld.name }}</span>
    </div>
    <p v-if="offline" class="small">
      {{ offline.chapters }} chapters and {{ offline.revisions }} snapshots (up to the last 30 of each) on this device · synced {{ when(offline.synced) }}
      <br />
      <span data-testid="offline-pictures">Pictures: {{ offline.pictures.count }} · {{ sizeText(offline.pictures.bytes) }}</span>
      <br />
      <span class="muted">
        Storage: {{ offline.persisted ? "kept by the browser" : "may be cleared when space runs low (install the app to keep it)" }} ·
        {{ mb(offline.usage) }} used
      </span>
    </p>
    <div class="actions">
      <button type="button" class="btn btn-sm" @click="syncNow">Sync now</button>
      <button type="button" class="btn btn-sm" @click="clearCopy">Remove from this device</button>
      <span v-if="offlineMsg" class="muted small">{{ offlineMsg }}</span>
    </div>
  </section>

  <section class="card">
    <div class="card-head"><h2>Recovery codes</h2></div>
    <RecoveryCodes v-if="newCodes" :codes="newCodes" @done="codesSaved" />
    <template v-else>
      <p>
        <span :class="{ 'pill warn': codesLeft !== null && codesLeft < 3 }">{{ codesLeft ?? "…" }} unused</span>
        <span class="muted"> · each signs you in once if you lose your passkeys.</span>
      </p>
      <button type="button" class="btn btn-sm" @click="regenerate">Make new codes</button>
    </template>
  </section>
</template>
