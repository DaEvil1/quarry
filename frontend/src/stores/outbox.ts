import { defineStore } from "pinia";

import { ApiError, post } from "../api";
import { localDb, type PendingCapture, type PendingCut } from "../localdb";

/**
 * Captures, and passages cut to the bin, waiting to reach the server. Each is stored on the device first and sent
 * from there, so writing a spark or cutting a passage never depends on having signal. Sending stops at the first
 * network failure and resumes when the browser says it is online again, when the app opens, and every minute while
 * anything is waiting.
 */
export const useOutbox = defineStore("outbox", {
  state: () => ({
    pending: [] as PendingCapture[],
    cuts: [] as PendingCut[],
    online: typeof navigator === "undefined" ? true : navigator.onLine,
    sending: false,
    needsSignIn: false,
  }),
  getters: {
    waiting: (s) => s.pending.filter((p) => !p.error).length + s.cuts.filter((c) => !c.error).length,
    failed: (s) => s.pending.filter((p) => p.error),
    forWorld: (s) => (world: string) => s.pending.filter((p) => p.world === world),
  },
  actions: {
    async refresh(): Promise<void> {
      try {
        this.pending = await localDb.outbox.orderBy("capturedAt").toArray();
        this.cuts = await localDb.pendingCuts.orderBy("cutAt").toArray();
      } catch {
        this.pending = [];
        this.cuts = [];
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

    /** Keep a cut on the device, then try to send it. Resolves true once the server has it. */
    async addCut(cut: Omit<PendingCut, "cutAt"> & Partial<PendingCut>): Promise<boolean> {
      const row: PendingCut = { ...cut, cutAt: cut.cutAt ?? new Date().toISOString() };
      await localDb.pendingCuts.put(row);
      await this.refresh();
      await this.send();
      return !this.cuts.some((c) => c.id === row.id);
    },

    /** Undo a cut that never left the device. Resolves false if it was sent already (remove it on the server). */
    async dropCut(id: string): Promise<boolean> {
      const there = await localDb.pendingCuts.get(id);
      if (there) await localDb.pendingCuts.delete(id);
      await this.refresh();
      return !!there;
    },

    async send(): Promise<void> {
      if (this.sending) return;
      this.sending = true;
      // one network failure stops everything; one refusal marks only that row
      const deliver = async (send: () => Promise<unknown>, done: () => Promise<unknown>, refused: (m: string) => Promise<unknown>) => {
        try {
          await send();
          await done();
          this.online = true;
          this.needsSignIn = false;
          return true;
        } catch (e) {
          const status = e instanceof ApiError ? e.status : 0;
          if (status === 0) {
            this.online = false;
            return false;
          }
          if (status === 401) {
            this.needsSignIn = true;
            return false;
          }
          if (status >= 500 || status === 429) return false;
          // refused for good (the world, project or chapter is gone, the text is invalid): keep it, marked
          await refused((e as Error).message);
          return true;
        }
      };
      try {
        let going = true;
        for (const p of await localDb.outbox.orderBy("capturedAt").toArray()) {
          if (p.error) continue;
          going = await deliver(
            () =>
              post(`/api/worlds/${encodeURIComponent(p.world)}/items`, {
                id: p.id,
                body: p.body,
                kind: p.kind,
                project: p.project,
                source: p.source,
                captured_at: p.capturedAt,
                entities: p.entities ?? [],
                chapter_id: p.chapterId ?? null,
              }),
            () => localDb.outbox.delete(p.id),
            (error) => localDb.outbox.update(p.id, { error }),
          );
          if (!going) break;
        }
        if (going) {
          for (const c of await localDb.pendingCuts.orderBy("cutAt").toArray()) {
            if (c.error) continue;
            going = await deliver(
              () =>
                post(`/api/worlds/${encodeURIComponent(c.world)}/cuts`, {
                  id: c.id,
                  chapter_id: c.chapterId,
                  body: c.body,
                  before: c.before,
                  after: c.after,
                  cut_at: c.cutAt,
                }),
              () => localDb.pendingCuts.delete(c.id),
              (error) => localDb.pendingCuts.update(c.id, { error }),
            );
            if (!going) break;
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
