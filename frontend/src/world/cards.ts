// The world's cards: every entry, small. The editor colours names and shows hover cards from these, so they are kept
// on the device (offline too) and refreshed whenever the bible changes.

import { defineStore } from "pinia";

import { get } from "../api";
import { localDb } from "../localdb";
import type { EntityKind, EntityRef, Gender, RelationType, Span, StoryChapter } from "../types";
import { Matcher } from "./matcher";
import { factsAsOf, holds, norm, type At, type IndexOf } from "./time";

export interface Card {
  id: string;
  name: string;
  kind: EntityKind;
  aliases: string[];
  first_name: string | null;
  match_case: boolean;
  exclusions: string[];
  summary: string;
  /** time bounds and outside time only when set (docs/SPEC.md §13.1.5) */
  facts: ({ label: string; value: string; from: string | null; until: string | null } & CardTimes)[];
  /** with a role in a group, for a type that has one (docs/SPEC.md §13.4) */
  relations: ({ label: string; other: EntityRef; standing: string; from: string | null; until: string | null; role?: string } & CardTimes)[];
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

export interface CardTimes {
  from_time?: number;
  from_approx?: boolean;
  until_time?: number;
  until_approx?: boolean;
  outside_time?: boolean;
}

/** A card's fact or relationship as a span on the clock. */
export const cardSpan = (x: { from: string | null; until: string | null } & CardTimes): Span => ({
  from_chapter_id: x.from,
  until_chapter_id: x.until,
  from_time: x.from_time ?? null,
  from_approx: x.from_approx,
  until_time: x.until_time ?? null,
  until_approx: x.until_approx,
  outside_time: x.outside_time,
});
const span = cardSpan;

/** Where an experiment's draft is read on the clock: as if it stood where its range stands (docs/SPEC.md §13.6.1). */
export interface DraftPoint {
  id: string;
  item: string;
  clock: number | null;
  set_time: number | null;
  set_approx: boolean;
  outside_time: boolean;
}

interface Kept {
  cards: Card[];
  ignored: string[];
  /** the world's kinds of relationship, for linking names from the editor */
  types?: RelationType[];
  /** the world's chapters in story order */
  timeline?: StoryChapter[];
  /** the labels with a switch set */
  switches?: LabelSwitch[];
  /** where open experiments' drafts are read on the clock */
  drafts?: DraftPoint[];
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
    drafts: [] as DraftPoint[],
    /** bumped on every change, so editors know to rebuild their matcher */
    version: 0,
  }),
  getters: {
    byId: (s) => new Map(s.cards.map((c) => [c.id, c])),
    names: (s): EntityRef[] => s.cards.map(({ id, name, kind }) => ({ id, name, kind })),
    /** a chapter's place on the clock, happened order (undefined for one that isn't on it: outside time, retired,
     * a draft), with the time each place is set at */
    indexOf: (s): IndexOf => {
      const m = new Map<string, number>();
      const t = new Map<number, number | null>();
      for (const c of s.timeline) {
        const place = c.clock === undefined ? c.index : c.clock;
        if (place === null) continue;
        m.set(c.id, place);
        t.set(place, c.early ? null : (c.set_time ?? null));
      }
      for (const d of s.drafts) if (d.clock !== null) t.set(d.clock, d.set_time);
      const f = ((id: string | null) => (id ? m.get(id) : undefined)) as IndexOf;
      f.timeOf = (place: number) => t.get(place);
      return f;
    },
    /** "as of" a chapter: its place on the clock, outside time, or for a draft where its range stands */
    pointOf: (s) => {
      const m = new Map<string, At>();
      for (const c of s.timeline) m.set(c.id, c.clock === null ? { outside: true } : c.clock === undefined ? c.index : c.clock);
      for (const d of s.drafts) m.set(d.id, d.outside_time ? { outside: true } : (d.clock ?? 0));
      return (id: string | null): At | undefined => (id ? m.get(id) : undefined);
    },
    /** the end of the story: the last place on the clock (null with no chapters) */
    lastPlace: (s): number | null => {
      const places = s.timeline.map((c) => (c.clock === undefined ? c.index : c.clock)).filter((p): p is number => p !== null);
      return places.length ? Math.max(...places) : null;
    },
    /** the chapter at the end of the story on the clock */
    endChapter: (s): string | null => {
      let best: StoryChapter | null = null;
      for (const c of s.timeline) {
        const p = c.clock === undefined ? c.index : c.clock;
        if (p !== null && (!best || p > (best.clock === undefined ? best.index : (best.clock ?? -1)))) best = c;
      }
      return best?.id ?? null;
    },
    /** any chapter has a time, a mark or is outside time: the clock isn't simply book order */
    timed: (s) => s.timeline.some((c) => c.time_at != null || !!c.outside_time || !!c.told_as),
    /** anything has a time (a chapter, or a bound): "as of" offers "At a time…" */
    anyTime: (s) =>
      s.timeline.some((c) => c.time_at != null) ||
      s.cards.some((c) => [...c.facts, ...c.relations].some((x) => x.from_time != null || x.until_time != null)),
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
        this.drafts = [];
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
        const [cards, ignored, types, timeline, labels, drafts] = await Promise.all([
          get<Card[]>(`${base}/cards`),
          get<string[]>(`${base}/name-ignores`),
          get<RelationType[]>(`${base}/relation-types`),
          get<StoryChapter[]>(`${base}/timeline`),
          get<LabelsPage>(`${base}/labels`),
          get<DraftPoint[]>(`${base}/draft-clock`).catch(() => [] as DraftPoint[]),
        ]);
        if (world !== this.world) return;
        const switches = switchesOf(labels);
        this.apply({ cards, ignored, types, timeline, switches, drafts });
        await localDb.kv.put({ key: key(world), value: JSON.parse(JSON.stringify({ cards, ignored, types, timeline, switches, drafts })) });
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
      this.drafts = kept.drafts ?? [];
      this.version++;
    },
    /** A card as it reads at a chapter (or a time): the facts and relationships that hold there (all of them for a
     * chapter not in the story, or none given). A draft is read where its range stands. */
    asOf(card: Card | undefined, chapter: string | null | { time: number }): Card | undefined {
      const at: At | undefined = chapter !== null && typeof chapter === "object" ? chapter : this.pointOf(chapter);
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
