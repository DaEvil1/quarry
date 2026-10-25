// The world's cards: every entry, small. The editor colours names and shows hover cards from these, so they are kept
// on the device (offline too) and refreshed whenever the bible changes.

import { defineStore } from "pinia";

import { get } from "../api";
import { localDb } from "../localdb";
import type { EntityKind, EntityRef, Gender, RelationType, StoryChapter } from "../types";
import { Matcher } from "./matcher";
import { factsAsOf, holds, norm } from "./time";

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
  /** with a role in a group, for a type that has one (docs/SPEC.md §13.4) */
  relations: { label: string; other: EntityRef; standing: string; from: string | null; until: string | null; role?: string }[];
  /** the labels of all its facts, whatever their standing, as compared (lower case) */
  labels?: string[];
  /** its level: a project's slug, or null for the world */
  project?: string | null;
  gender?: Gender | null;
}

/** A label's switches for a kind (docs/SPEC.md §12.6.4, §12.6.5). */
export interface LabelSwitch {
  kind: EntityKind;
  label: string;
  several: boolean;
  expected: boolean;
}

const span = (x: { from: string | null; until: string | null }) => ({ from_chapter_id: x.from, until_chapter_id: x.until });

interface Kept {
  cards: Card[];
  ignored: string[];
  /** the world's kinds of relationship, for linking names from the editor */
  types?: RelationType[];
  /** the world's chapters in story order */
  timeline?: StoryChapter[];
  /** the labels with a switch set */
  switches?: LabelSwitch[];
}

const key = (world: string) => `cards:${world}`;

export const useCards = defineStore("cards", {
  state: () => ({
    world: "" as string,
    cards: [] as Card[],
    ignored: [] as string[],
    types: [] as RelationType[],
    timeline: [] as StoryChapter[],
    switches: [] as LabelSwitch[],
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
    /** does this label hold several values at once for this kind? */
    several: (s) => {
      const on = new Set(s.switches.filter((x) => x.several).map((x) => `${x.kind}|${norm(x.label)}`));
      return (kind: string, label: string) => on.has(`${kind}|${norm(label)}`);
    },
    /** the labels expected on every entry of a kind */
    expected: (s) => {
      const out = new Map<string, string[]>();
      for (const x of s.switches) if (x.expected) out.set(x.kind, [...(out.get(x.kind) ?? []), x.label]);
      return (kind: string) => out.get(kind) ?? [];
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
        this.switches = [];
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
        const [cards, ignored, types, timeline, labels] = await Promise.all([
          get<Card[]>(`${base}/cards`),
          get<string[]>(`${base}/name-ignores`),
          get<RelationType[]>(`${base}/relation-types`),
          get<StoryChapter[]>(`${base}/timeline`),
          get<LabelsPage>(`${base}/labels`),
        ]);
        if (world !== this.world) return;
        const switches = switchesOf(labels);
        this.apply({ cards, ignored, types, timeline, switches });
        await localDb.kv.put({ key: key(world), value: JSON.parse(JSON.stringify({ cards, ignored, types, timeline, switches })) });
      } catch {
        /* offline: keep what we have */
      }
    },
    apply(kept: Kept) {
      this.cards = kept.cards;
      this.ignored = kept.ignored;
      this.types = kept.types ?? [];
      this.timeline = kept.timeline ?? [];
      this.switches = kept.switches ?? [];
      this.version++;
    },
    /** A card as it reads at a chapter: the facts and relationships that hold there (all of them for a chapter
     * outside the story, or none given). */
    asOf(card: Card | undefined, chapterId: string | null): Card | undefined {
      const at = this.indexOf(chapterId);
      if (!card || at === undefined) return card;
      const indexOf = this.indexOf;
      const several = (label: string) => this.several(card.kind, label);
      const facts = factsAsOf(card.facts.map((f) => ({ ...f, ...span(f) })), at, indexOf, several).map(({ label, value, from, until }) => ({ label, value, from, until }));
      return { ...card, facts, relations: card.relations.filter((r) => holds(span(r), at, indexOf)) };
    },
    matcher(): Matcher {
      return new Matcher(this.cards, this.ignored);
    },
  },
});

/** The Labels page's data (GET /labels): per kind, its labels with counts, values and switches. */
export interface LabelsPage {
  kinds: {
    kind: EntityKind;
    total: number;
    labels: {
      label: string;
      count: number;
      values: { value: string; count: number; entries: EntityRef[] }[];
      several: boolean;
      expected: boolean;
      asked: boolean;
      without: (EntityRef & { resolved: boolean })[];
    }[];
  }[];
  /** roles in groups, with the per-role "one at a time" switch (docs/SPEC.md §13.4) */
  roles?: { role: string; count: number; one_at_a_time: boolean; types: string[]; groups: EntityRef[] }[];
}

export function switchesOf(page: LabelsPage): LabelSwitch[] {
  return page.kinds.flatMap((k) => k.labels.filter((l) => l.several || l.expected).map((l) => ({ kind: k.kind, label: l.label, several: l.several, expected: l.expected })));
}
