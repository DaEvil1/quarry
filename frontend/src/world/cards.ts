// The world's cards: every entry, small. The editor colours names and shows hover cards from these, so they are kept
// on the device (offline too) and refreshed whenever the bible changes.

import { defineStore } from "pinia";

import { get } from "../api";
import { localDb } from "../localdb";
import type { EntityKind, EntityRef, Gender, RelationType, Span, StoryChapter } from "../types";
import { ageAt, eraAt, erasOf, eventTime, type Era } from "./eras";
import { timeText, type Unit } from "./when";
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
  /** time bounds and outside time only when set (docs/SPEC.md §13.1.5); `planned` on a card read in the Journal */
  facts: ({ label: string; value: string; from: string | null; until: string | null; planned?: boolean } & CardTimes)[];
  /** its planned facts, apart: cards in the Journal show them, marked (docs/SPEC.md §14.1.1) */
  planned?: ({ label: string; value: string; from: string | null; until: string | null } & CardTimes)[];
  /** with a role in a group, for a type that has one (docs/SPEC.md §13.4) */
  relations: ({ label: string; other: EntityRef; standing: string; from: string | null; until: string | null; role?: string } & CardTimes)[];
  /** the labels of all its facts, whatever their standing, as compared (lower case) */
  labels?: string[];
  /** its level: a project's slug, or null for the world */
  project?: string | null;
  gender?: Gender | null;
  /** the kinds it is as well, in the order added (docs/SPEC.md §14.8) */
  also_kinds?: EntityKind[];
  /** an event's when (a chapter, a time, or outside time), and an era's colour (docs/SPEC.md §13.2.1) */
  when?: { chapter: string | null; at: number | null; end: number | null; label: string | null; approx: boolean; outside: boolean };
  era_colour?: string;
  /** as of a chapter: a character's age there ("age 34", "not born yet", "died at 61") */
  age?: string;
  /** an event's time in words with its era ("year 312 · the Lamp Years"), worked out when the cards load */
  whenText?: string;
  whenColour?: string;
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
  /** what the world counts time in */
  unit?: Unit;
}

const key = (world: string) => `cards:${world}`;

/** An entry's kinds: the main one first, then the ones added (docs/SPEC.md §14.8). */
export const kindsOf = (c: Pick<Card, "kind" | "also_kinds">): EntityKind[] => [c.kind, ...(c.also_kinds ?? [])];

export const useCards = defineStore("cards", {
  state: () => ({
    world: "" as string,
    cards: [] as Card[],
    ignored: [] as string[],
    types: [] as RelationType[],
    timeline: [] as StoryChapter[],
    switches: [] as LabelSwitch[],
    drafts: [] as DraftPoint[],
    unit: { unit: "year", units: "years" } as Unit,
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
    /** the world's eras, from the events whose type is "era" (docs/SPEC.md §13.2.1) */
    eras: (s): Era[] => erasOf(s.cards, s.timeline),
    /** the era a time is in (null for none) */
    eraOf(): (t: number | null | undefined) => Era | null {
      const eras = this.eras;
      return (t) => eraAt(t, eras);
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
    /** counted under each of its kinds (docs/SPEC.md §14.8) */
    counts: (s) => {
      const out: Partial<Record<EntityKind, number>> = {};
      for (const c of s.cards) for (const k of kindsOf(c)) out[k] = (out[k] ?? 0) + 1;
      return out;
    },
    /** does this entry have this kind, main or added? */
    hasKind(): (id: string, kind: string) => boolean {
      const byId = this.byId;
      return (id, kind) => {
        const c = byId.get(id);
        return !!c && kindsOf(c).includes(kind as EntityKind);
      };
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
        const [cards, ignored, types, timeline, labels, drafts, w] = await Promise.all([
          get<Card[]>(`${base}/cards`),
          get<string[]>(`${base}/name-ignores`),
          get<RelationType[]>(`${base}/relation-types`),
          get<StoryChapter[]>(`${base}/timeline`),
          get<LabelsPage>(`${base}/labels`),
          get<DraftPoint[]>(`${base}/draft-clock`).catch(() => [] as DraftPoint[]),
          get<{ time_unit?: string; time_units?: string }>(base).catch(() => ({}) as { time_unit?: string; time_units?: string }),
        ]);
        if (world !== this.world) return;
        const switches = switchesOf(labels);
        const unit = { unit: w.time_unit || "year", units: w.time_units || "years" };
        this.apply({ cards, ignored, types, timeline, switches, drafts, unit });
        await localDb.kv.put({ key: key(world), value: JSON.parse(JSON.stringify({ cards, ignored, types, timeline, switches, drafts, unit })) });
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
      this.unit = kept.unit ?? { unit: "year", units: "years" };
      // an event's time in words, with its era, for its card
      const chapters = new Map(this.timeline.map((c) => [c.id, c]));
      const eras = erasOf(this.cards, this.timeline);
      for (const c of this.cards) {
        if (c.kind !== "event" || !c.when) continue;
        const t = eventTime(c, chapters);
        const own = c.when.outside ? "outside time" : c.when.at != null ? timeText({ time_at: c.when.at, time_end: c.when.end, time_label: c.when.label, time_approx: c.when.approx }, this.unit) : t ? timeText({ time_at: t.t, time_approx: t.approx }, this.unit) : "";
        const era = eraAt(t?.t, eras);
        c.whenText = own && era && era.id !== c.id ? `${own} · ${era.name}` : own;
        c.whenColour = era && era.id !== c.id ? era.colour : undefined;
      }
      this.version++;
    },
    /** A card as it reads at a chapter (or a time): the facts and relationships that hold there (all of them for a
     * chapter not in the story, or none given). A draft is read where its range stands. */
    asOf(card: Card | undefined, chapter: string | null | { time: number }): Card | undefined {
      const at: At | undefined = chapter !== null && typeof chapter === "object" ? chapter : this.pointOf(chapter);
      if (!card || at === undefined) return card;
      const indexOf = this.indexOf;
      const several = (label: string) => this.several(card.kind, label);
      const facts = factsAsOf(card.facts.map((f) => ({ ...f, ...span(f) })), at, indexOf, several).map(({ label, value, from, until, outside_time }) => ({ label, value, from, until, outside_time }));
      // a character's age there, worked out from their birth (docs/SPEC.md §13.2.4)
      const age = typeof at === "number" && card.kind === "character" ? ageAt(card, at, indexOf, this.byId, new Map(this.timeline.map((c) => [c.id, c]))) : "";
      return { ...card, facts, relations: card.relations.filter((r) => holds(span(r), at, indexOf)), ...(age ? { age } : {}) };
    },
    /** A card as a journal entry shows it (docs/SPEC.md §14.1.1): as of the end of the story unless a chapter or a
     * time is chosen, with its planned facts too, marked, since in planning they are often all there is. */
    inPlanning(card: Card | undefined, at: string | null | { time: number }): Card | undefined {
      if (!card) return card;
      const point = at ?? this.endChapter;
      const read = this.asOf(card, point) ?? card;
      if (!card.planned?.length) return read;
      const planned = this.asOf({ ...card, facts: card.planned }, point)?.facts ?? card.planned;
      return { ...read, facts: [...read.facts, ...planned.map((f) => ({ ...f, planned: true }))] };
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
