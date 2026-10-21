import { defineStore } from "pinia";

import { ApiError, get, post } from "../api";
import { clearMeSnapshot, readMeSnapshot, saveMeSnapshot } from "../localdb";
import type { ItemCounts, Me, Project, World } from "../types";

/** Who is signed in, and the worlds and projects they can open. */
export const useSession = defineStore("session", {
  state: () => ({
    me: null as Me | null,
    /** the server could not be reached; `me` is the copy saved on this device */
    offline: false,
    /** open and deferred counts of the world shown in the nav */
    counts: null as (ItemCounts & { world: string }) | null,
    /** how many words in the world look like misspelled names (the name check's badge) */
    nearMisses: null as { world: string; words: number } | null,
  }),
  getters: {
    user: (s) => s.me?.user ?? null,
    worlds: (s): World[] => s.me?.worlds ?? [],
  },
  actions: {
    /**
     * Fetch the signed-in user; returns false (and clears state) when nobody is signed in. Without a network it
     * falls back to the copy saved on this device, so the app (and capturing) still works offline.
     */
    async load(): Promise<boolean> {
      try {
        this.me = await get<Me>("/api/me");
        this.offline = false;
        await saveMeSnapshot(this.me);
        return true;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          this.me = null;
          await clearMeSnapshot();
          return false;
        }
        if (e instanceof ApiError && e.status === 0) {
          const saved = await readMeSnapshot();
          if (saved) {
            this.me = saved;
            this.offline = true;
            return true;
          }
        }
        throw e;
      }
    },
    async signOut(): Promise<void> {
      await post("/api/auth/logout");
      this.me = null;
      this.counts = null;
      await clearMeSnapshot();
    },
    world(slug: string): World | undefined {
      return this.worlds.find((w) => w.slug === slug);
    },
    project(worldSlug: string, projectSlug: string): Project | undefined {
      return this.world(worldSlug)?.projects.find((p) => p.slug === projectSlug);
    },
    /** Put a world (new or changed) into the list, replacing the old copy and keeping name order. */
    putWorld(world: World, oldSlug?: string): void {
      if (!this.me) return;
      const rest = this.me.worlds.filter((w) => w.id !== world.id && w.slug !== oldSlug);
      this.me.worlds = [...rest, world].sort((a, b) => a.name.localeCompare(b.name));
      void saveMeSnapshot(this.me);
    },
    async refreshNearMisses(world: string): Promise<void> {
      try {
        const c = await get<{ words: number }>(`/api/worlds/${encodeURIComponent(world)}/near-misses/count`);
        this.nearMisses = { world, words: c.words };
      } catch {
        /* offline: keep what we had */
      }
    },
    /** Refresh the inbox counts shown in the nav; quietly keeps the old ones when offline. */
    async refreshCounts(world: string): Promise<void> {
      try {
        const c = await get<ItemCounts>(`/api/worlds/${encodeURIComponent(world)}/items/counts`);
        this.counts = { ...c, world };
      } catch {
        /* offline or gone: keep what we had */
      }
    },
  },
});
