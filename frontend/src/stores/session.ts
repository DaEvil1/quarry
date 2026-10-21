import { defineStore } from "pinia";

import { ApiError, get, post } from "../api";
import type { Me, Project, World } from "../types";

/** Who is signed in, and the worlds and projects they can open. */
export const useSession = defineStore("session", {
  state: () => ({
    me: null as Me | null,
  }),
  getters: {
    user: (s) => s.me?.user ?? null,
    worlds: (s): World[] => s.me?.worlds ?? [],
  },
  actions: {
    /** Fetch the signed-in user; returns false (and clears state) when nobody is signed in. */
    async load(): Promise<boolean> {
      try {
        this.me = await get<Me>("/api/me");
        return true;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          this.me = null;
          return false;
        }
        throw e;
      }
    },
    async signOut(): Promise<void> {
      await post("/api/auth/logout");
      this.me = null;
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
    },
  },
});
