<script setup lang="ts">
import { diffWords } from "diff";
import { computed, onMounted, ref } from "vue";

import { unreachable } from "../api";
import { listEntryRevisions } from "../journal";
import { getRevision, listRevisions, REASON_LABELS, type RevisionInfo } from "../manuscript";
import { localRevision, localRevisions } from "../offline";

// A chapter's (or a journal entry's) snapshots, newest first. Choosing one shows what changed since (word by word) or
// the old text on its own (to copy a passage); it can be put back, and the text it replaces is kept as a snapshot
// first.
const props = defineProps<{ world: string; chapterId: string; current: string; doc?: "chapter" | "journal" }>();
const emit = defineEmits<{ restore: [revisionId: string, body: string]; close: [] }>();
// the server couldn't be reached: the snapshots kept on this device (the last 30)
const local = ref(false);
const offline = unreachable;

const revisions = ref<RevisionInfo[]>([]);
const chosen = ref<(RevisionInfo & { body: string }) | null>(null);
const mode = ref<"diff" | "text">("diff");
const error = ref("");

const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

onMounted(async () => {
  try {
    revisions.value = props.doc === "journal" ? await listEntryRevisions(props.world, props.chapterId) : await listRevisions(props.world, props.chapterId);
  } catch (e) {
    if (!offline(e)) {
      error.value = (e as Error).message;
      return;
    }
    local.value = true;
    revisions.value = await localRevisions(props.chapterId);
  }
});

async function choose(r: RevisionInfo) {
  error.value = "";
  try {
    chosen.value = local.value ? ((await localRevision(r.id)) ?? null) : await getRevision(props.world, r.id);
  } catch (e) {
    if (!offline(e)) {
      error.value = (e as Error).message;
      return;
    }
    local.value = true;
    chosen.value = (await localRevision(r.id)) ?? null;
    if (!chosen.value) error.value = "That snapshot isn't on this device.";
  }
}

const parts = computed(() => (chosen.value ? diffWords(chosen.value.body, props.current) : []));
const unchanged = computed(() => parts.value.every((p) => !p.added && !p.removed));
</script>

<template>
  <aside class="drawer" aria-label="History" data-testid="history">
    <div class="drawer-head">
      <h2>History</h2>
      <button type="button" class="icon-btn" aria-label="Close history" @click="emit('close')">✕</button>
    </div>
    <div v-if="error" class="notice error small">{{ error }}</div>
    <div v-if="local" class="notice offline small" data-testid="history-offline">Offline: the last {{ revisions.length }} snapshots kept on this device.</div>
    <div class="drawer-body">
      <ul class="revisions">
        <li v-for="r in revisions" :key="r.id">
          <button type="button" :class="{ active: chosen?.id === r.id }" @click="choose(r)">
            <span>{{ r.label || REASON_LABELS[r.reason] }}</span>
            <span class="muted small">{{ fmt.format(new Date(r.created_at)) }} · {{ r.words }} words</span>
          </button>
        </li>
        <li v-if="!revisions.length" class="empty small">No snapshots yet. One is kept when you pause, leave or press Ctrl+S.</li>
      </ul>
      <div v-if="chosen" class="revision-view">
        <div class="actions">
          <div class="tabs" role="tablist">
            <button type="button" role="tab" class="tab" :aria-selected="mode === 'diff'" @click="mode = 'diff'">Changes since</button>
            <button type="button" role="tab" class="tab" :aria-selected="mode === 'text'" @click="mode = 'text'">This version</button>
          </div>
          <span class="spacer" />
          <button type="button" class="btn btn-sm btn-primary" @click="emit('restore', chosen.id, chosen.body)">Restore this version</button>
        </div>
        <p v-if="mode === 'diff' && unchanged" class="muted small">Same as now.</p>
        <div v-if="mode === 'diff'" class="diff prose">
          <template v-for="(p, i) in parts" :key="i">
            <ins v-if="p.added">{{ p.value }}</ins><del v-else-if="p.removed">{{ p.value }}</del><span v-else>{{ p.value }}</span>
          </template>
        </div>
        <div v-else class="diff prose">{{ chosen.body }}</div>
      </div>
    </div>
  </aside>
</template>
