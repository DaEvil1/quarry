// The browser's own database (IndexedDB via Dexie): captures waiting to be sent, a copy of who is signed in so the
// app still opens without a network, and the offline copy of the manuscript: every chapter of the worlds opened on
// this device, the last 30 snapshots of each, and text written but not yet saved; and the same for journal entries
// (docs/SPEC.md §14.1.1), with entries made offline waiting to be sent.

import Dexie, { type EntityTable } from "dexie";

import type { Chapter } from "./manuscript";
import type { ItemKind, JournalDetail, Me } from "./types";

/** A capture saved on this device that the server has not confirmed yet. */
export interface PendingCapture {
  /** chosen here, so sending it twice still makes one item */
  id: string;
  world: string;
  body: string;
  kind: Exclude<ItemKind, "experiment">;
  project: string | null;
  source: string;
  capturedAt: string;
  /** bible entries it is tagged with */
  entities?: string[];
  /** the chapter it was thought of in (a thought stashed while writing), or the journal entry */
  chapterId?: string;
  journalId?: string;
  /** made from a plan's passage: the chapters ticked (docs/SPEC.md §18.4) */
  chapterIds?: string[];
  /** made from a selection: the passage (docs/SPEC.md §14.3.1) */
  passage?: string;
  /** "Park it": saved as deferred instead of open */
  status?: "open" | "deferred";
  /** the server refused it (not a network problem); kept so nothing is lost silently */
  error?: string;
}

interface Kv {
  key: string;
  value: unknown;
}

export interface LocalChapter extends Chapter {
  world: string;
}

export interface LocalRevision {
  id: string;
  chapterId: string;
  version: number;
  title: string;
  body: string;
  reason: "autosnap" | "checkpoint" | "state" | "restore" | "conflict" | "start";
  label: string | null;
  words: number;
  created_at: string;
}

/** A journal entry kept on this device (docs/SPEC.md §14.1.1). */
export interface LocalEntry extends JournalDetail {
  world: string;
}

/** A journal entry made on this device that the server has not confirmed yet (it waits like a capture). */
export interface PendingEntry {
  /** chosen here, so sending it twice still makes one entry */
  id: string;
  world: string;
  entry_date: string;
  title: string | null;
  project: string | null;
  /** the server refused it (not a network problem); kept so nothing is lost silently */
  error?: string;
}

/** Text typed on this device that the server hasn't confirmed yet; survives reloads and going offline. */
export interface Draft {
  /** the chapter's id, or the journal entry's (see `doc`) */
  chapterId: string;
  /** a journal entry's text; a chapter's when absent */
  doc?: "journal";
  world: string;
  title: string;
  body: string;
  /** the version this text was written on top of */
  baseVersion: number;
  savedAt: string;
}

/** A snapshot made on this device while offline (an offline restore), waiting to be sent. */
export interface PendingRevision {
  id: string;
  world: string;
  /** the chapter's id, or the journal entry's (see `doc`) */
  chapterId: string;
  doc?: "journal";
  reason: "restore" | "conflict";
  label: string;
  body: string;
}

/** A passage cut to the bin on this device that the server has not confirmed yet (it waits like a capture). */
export interface PendingCut {
  /** chosen here, so sending it twice still makes one cut */
  id: string;
  world: string;
  chapterId: string;
  body: string;
  /** up to 80 characters either side, to find the place again */
  before: string;
  after: string;
  cutAt: string;
  /** the server refused it (not a network problem); kept so nothing is lost silently */
  error?: string;
}

/** A labelled checkpoint older than the last 30 snapshots, fetched once to show changes since it, then kept. */
export interface KeptCheckpoint {
  id: string;
  chapterId: string;
  label: string;
  body: string;
  created_at: string;
}

class LocalDb extends Dexie {
  outbox!: EntityTable<PendingCapture, "id">;
  kv!: EntityTable<Kv, "key">;
  chapters!: EntityTable<LocalChapter, "id">;
  revisions!: EntityTable<LocalRevision, "id">;
  drafts!: EntityTable<Draft, "chapterId">;
  pendingRevisions!: EntityTable<PendingRevision, "id">;
  pendingCuts!: EntityTable<PendingCut, "id">;
  checkpoints!: EntityTable<KeptCheckpoint, "id">;
  journal!: EntityTable<LocalEntry, "id">;
  pendingEntries!: EntityTable<PendingEntry, "id">;

  constructor() {
    super("quarry");
    this.version(1).stores({
      outbox: "id, world, capturedAt",
      kv: "key",
    });
    this.version(2).stores({
      chapters: "id, world",
      revisions: "id, chapterId, created_at",
      drafts: "chapterId, world",
      pendingRevisions: "id, world",
    });
    this.version(3).stores({
      pendingCuts: "id, world, cutAt",
      checkpoints: "id, chapterId",
    });
    this.version(4).stores({
      journal: "id, world",
      pendingEntries: "id, world",
    });
  }
}

export const localDb = new LocalDb();

export async function saveMeSnapshot(me: Me): Promise<void> {
  try {
    // a plain copy: IndexedDB cannot store Vue's reactive proxies
    await localDb.kv.put({ key: "me", value: JSON.parse(JSON.stringify(me)) as Me });
  } catch {
    /* storage unavailable: the app then needs the network to open */
  }
}

export async function readMeSnapshot(): Promise<Me | null> {
  try {
    const row = await localDb.kv.get("me");
    return (row?.value as Me | undefined) ?? null;
  } catch {
    return null;
  }
}

export async function clearMeSnapshot(): Promise<void> {
  try {
    await localDb.kv.delete("me");
  } catch {
    /* nothing to clear */
  }
}
