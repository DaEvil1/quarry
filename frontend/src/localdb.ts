// The browser's own database (IndexedDB via Dexie): captures waiting to be sent, and a copy of who is signed in so
// the app still opens without a network. Phase 5 adds the local copy of everything else here.

import Dexie, { type EntityTable } from "dexie";

import type { ItemKind, Me } from "./types";

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
  /** the server refused it (not a network problem); kept so nothing is lost silently */
  error?: string;
}

interface Kv {
  key: string;
  value: unknown;
}

class LocalDb extends Dexie {
  outbox!: EntityTable<PendingCapture, "id">;
  kv!: EntityTable<Kv, "key">;

  constructor() {
    super("quarry");
    this.version(1).stores({
      outbox: "id, world, capturedAt",
      kv: "key",
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
