import { defineStore } from "pinia";

import { ApiError, post } from "../api";
import { localDb, type PendingCapture } from "../localdb";

/**
 * Captures waiting to reach the server. A capture is stored on the device first and sent from there, so writing a
 * spark never depends on having signal. Sending stops at the first network failure and resumes when the browser
 * says it is online again, when the app opens, and every minute while anything is waiting.
 */
export const useOutbox = defineStore("outbox", {
  state: () => ({
    pending: [] as PendingCapture[],
    online: typeof navigator === "undefined" ? true : navigator.onLine,
    sending: false,
    needsSignIn: false,
  }),
  getters: {
    waiting: (s) => s.pending.filter((p) => !p.error).length,
    failed: (s) => s.pending.filter((p) => p.error),
    forWorld: (s) => (world: string) => s.pending.filter((p) => p.world === world),
  },
  actions: {
    async refresh(): Promise<void> {
      try {
        this.pending = await localDb.outbox.orderBy("capturedAt").toArray();
      } catch {
        this.pending = [];
      }
    },

    /** Keep a capture on the device, then try to send it. Resolves true once the server has it. */
    async add(capture: Omit<PendingCapture, "id" | "capturedAt"> & Partial<PendingCapture>): Promise<boolean> {
      const row: PendingCapture = {
        id: capture.id ?? crypto.randomUUID(),
        capturedAt: capture.capturedAt ?? new Date().toISOString(),
        world: capture.world,
        body: capture.body,
        kind: capture.kind,
        project: capture.project,
        source: capture.source,
        entities: capture.entities ?? [],
        chapterId: capture.chapterId,
      };
      await localDb.outbox.put(row);
      await this.refresh();
      await this.send();
      return !this.pending.some((p) => p.id === row.id);
    },

    async send(): Promise<void> {
      if (this.sending) return;
      this.sending = true;
      try {
        for (const p of await localDb.outbox.orderBy("capturedAt").toArray()) {
          if (p.error) continue;
          try {
            await post(`/api/worlds/${encodeURIComponent(p.world)}/items`, {
              id: p.id,
              body: p.body,
              kind: p.kind,
              project: p.project,
              source: p.source,
              captured_at: p.capturedAt,
              entities: p.entities ?? [],
              chapter_id: p.chapterId ?? null,
            });
            await localDb.outbox.delete(p.id);
            this.online = true;
            this.needsSignIn = false;
          } catch (e) {
            const status = e instanceof ApiError ? e.status : 0;
            if (status === 0) {
              this.online = false;
              break;
            }
            if (status === 401) {
              this.needsSignIn = true;
              break;
            }
            if (status >= 500 || status === 429) break;
            // refused for good (the world or project is gone, the text is invalid): keep it, marked
            await localDb.outbox.update(p.id, { error: (e as Error).message });
          }
        }
      } finally {
        this.sending = false;
        await this.refresh();
      }
    },

    /** Try a refused capture again, e.g. after fixing its project. */
    async retry(id: string, changes: Partial<PendingCapture> = {}): Promise<void> {
      await localDb.outbox.update(id, { ...changes, error: undefined });
      await this.refresh();
      await this.send();
    },

    async discard(id: string): Promise<void> {
      await localDb.outbox.delete(id);
      await this.refresh();
    },

    /** Start listening for connectivity; call once when the app starts. */
    watch(): void {
      if (typeof window === "undefined") return;
      window.addEventListener("online", () => {
        this.online = true;
        void this.send();
      });
      window.addEventListener("offline", () => (this.online = false));
      setInterval(() => {
        if (this.waiting) void this.send();
      }, 60_000);
      void this.refresh().then(() => this.send());
    },
  },
});
