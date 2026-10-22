// The world's cards: every entry, small. The editor colours names and shows hover cards from these, so they are kept
// on the device (offline too) and refreshed whenever the bible changes.

import { defineStore } from "pinia";

import { get } from "../api";
import { localDb } from "../localdb";
import type { EntityKind, EntityRef } from "../types";
import { Matcher } from "./matcher";

export interface Card {
  id: string;
  name: string;
  kind: EntityKind;
  aliases: string[];
  first_name: string | null;
  match_case: boolean;
  exclusions: string[];
  summary: string;
  facts: { label: string; value: string }[];
  relations: { label: string; other: EntityRef; standing: string }[];
}

interface Kept {
  cards: Card[];
  ignored: string[];
}

const key = (world: string) => `cards:${world}`;

export const useCards = defineStore("cards", {
  state: () => ({
    world: "" as string,
    cards: [] as Card[],
    ignored: [] as string[],
    /** bumped on every change, so editors know to rebuild their matcher */
    version: 0,
  }),
  getters: {
    byId: (s) => new Map(s.cards.map((c) => [c.id, c])),
    names: (s): EntityRef[] => s.cards.map(({ id, name, kind }) => ({ id, name, kind })),
    counts: (s) => {
      const out: Partial<Record<EntityKind, number>> = {};
      for (const c of s.cards) out[c.kind] = (out[c.kind] ?? 0) + 1;
      return out;
    },
  },
  actions: {
    /** Load a world's cards: the copy on this device first (instant, offline), then the server's. */
    async load(world: string, force = false): Promise<void> {
      if (world !== this.world) {
        this.world = world;
        this.cards = [];
        this.ignored = [];
        try {
          const kept = (await localDb.kv.get(key(world)))?.value as Kept | undefined;
          if (kept && this.world === world) this.apply(kept);
        } catch {
          /* nothing kept */
        }
      } else if (!force && this.cards.length) {
        void this.refresh(world);
        return;
      }
      await this.refresh(world);
    },
    async refresh(worldArg?: string): Promise<void> {
      const world = worldArg ?? this.world;
      if (!world) return;
      try {
        const base = `/api/worlds/${encodeURIComponent(world)}`;
        const [cards, ignored] = await Promise.all([get<Card[]>(`${base}/cards`), get<string[]>(`${base}/name-ignores`)]);
        if (world !== this.world) return;
        this.apply({ cards, ignored });
        await localDb.kv.put({ key: key(world), value: JSON.parse(JSON.stringify({ cards, ignored })) });
      } catch {
        /* offline: keep what we have */
      }
    },
    apply(kept: Kept) {
      this.cards = kept.cards;
      this.ignored = kept.ignored;
      this.version++;
    },
    matcher(): Matcher {
      return new Matcher(this.cards, this.ignored);
    },
  },
});
