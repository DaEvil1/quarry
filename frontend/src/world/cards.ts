// The world's cards: every entry, small. The editor colours names and shows hover cards from these, so they are kept
// on the device (offline too) and refreshed whenever the bible changes.

import { defineStore } from "pinia";

import { get } from "../api";
import { localDb } from "../localdb";
import type { EntityKind, EntityRef, RelationType, StoryChapter } from "../types";
import { Matcher } from "./matcher";
import { factsAsOf, holds } from "./time";

export interface Card {
  id: string;
  name: string;
  kind: EntityKind;
  aliases: string[];
  first_name: string | null;
  match_case: boolean;
  exclusions: string[];
  summary: string;
  facts: { label: string; value: string; from: string | null; until: string | null }[];
  relations: { label: string; other: EntityRef; standing: string; from: string | null; until: string | null }[];
}

const span = (x: { from: string | null; until: string | null }) => ({ from_chapter_id: x.from, until_chapter_id: x.until });

interface Kept {
  cards: Card[];
  ignored: string[];
  /** the world's kinds of relationship, for linking names from the editor */
  types?: RelationType[];
  /** the world's chapters in story order */
  timeline?: StoryChapter[];
}

const key = (world: string) => `cards:${world}`;

export const useCards = defineStore("cards", {
  state: () => ({
    world: "" as string,
    cards: [] as Card[],
    ignored: [] as string[],
    types: [] as RelationType[],
    timeline: [] as StoryChapter[],
    /** bumped on every change, so editors know to rebuild their matcher */
    version: 0,
  }),
  getters: {
    byId: (s) => new Map(s.cards.map((c) => [c.id, c])),
    names: (s): EntityRef[] => s.cards.map(({ id, name, kind }) => ({ id, name, kind })),
    /** a chapter's place in the story (undefined for one that isn't in it) */
    indexOf: (s) => {
      const m = new Map(s.timeline.map((c) => [c.id, c.index]));
      return (id: string | null) => (id ? m.get(id) : undefined);
    },
    chapterTitle: (s) => {
      const m = new Map(s.timeline.map((c) => [c.id, c.title]));
      return (id: string) => m.get(id);
    },
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
        this.types = [];
        this.timeline = [];
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
        const [cards, ignored, types, timeline] = await Promise.all([
          get<Card[]>(`${base}/cards`),
          get<string[]>(`${base}/name-ignores`),
          get<RelationType[]>(`${base}/relation-types`),
          get<StoryChapter[]>(`${base}/timeline`),
        ]);
        if (world !== this.world) return;
        this.apply({ cards, ignored, types, timeline });
        await localDb.kv.put({ key: key(world), value: JSON.parse(JSON.stringify({ cards, ignored, types, timeline })) });
      } catch {
        /* offline: keep what we have */
      }
    },
    apply(kept: Kept) {
      this.cards = kept.cards;
      this.ignored = kept.ignored;
      this.types = kept.types ?? [];
      this.timeline = kept.timeline ?? [];
      this.version++;
    },
    /** A card as it reads at a chapter: the facts and relationships that hold there (all of them for a chapter
     * outside the story, or none given). */
    asOf(card: Card | undefined, chapterId: string | null): Card | undefined {
      const at = this.indexOf(chapterId);
      if (!card || at === undefined) return card;
      const indexOf = this.indexOf;
      const facts = factsAsOf(card.facts.map((f) => ({ ...f, ...span(f) })), at, indexOf).map(({ label, value, from, until }) => ({ label, value, from, until }));
      return { ...card, facts, relations: card.relations.filter((r) => holds(span(r), at, indexOf)) };
    },
    matcher(): Matcher {
      return new Matcher(this.cards, this.ignored);
    },
  },
});
