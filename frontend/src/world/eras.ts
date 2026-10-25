// Eras and ages, from the cards (docs/SPEC.md §13.2.1, §13.2.4), worked out on the device. An era is an event whose
// type is "era" (whatever the capitals) with a span: one with no end runs on to the end of time. A time's era is the
// innermost era holding it; between two that overlap without nesting, the one that starts later. An age is a set
// time minus the birth time, rounded down, "about" when either is approximate.

import type { StoryChapter } from "../types";
import type { Card } from "./cards";
import { holds, norm, type IndexOf } from "./time";

export const ERA_COLOURS = ["amber", "moss", "teal", "sky", "indigo", "plum", "rose", "rust"] as const;
export type EraColour = (typeof ERA_COLOURS)[number];

export interface Era {
  id: string;
  name: string;
  colour: EraColour;
  start: number;
  /** null: it runs on to the end of time */
  end: number | null;
  approx: boolean;
  /** how many eras it is nested in (0 for the outermost) */
  depth: number;
}

const isType = (c: Card, value: string) => c.facts.some((f) => norm(f.label) === "type" && norm(f.value) === value);

/** When an event happens on the axis: its own time, or the set time of the chapter it happens in (null when neither,
 * outside time, or not placed yet). */
export function eventTime(c: Card, chapters: Map<string, StoryChapter>): { t: number; end: number | null; approx: boolean } | null {
  const w = c.when;
  if (!w || w.outside) return null;
  if (w.at != null) return { t: w.at, end: w.end ?? null, approx: !!w.approx };
  const ch = w.chapter ? chapters.get(w.chapter) : undefined;
  if (ch && !ch.early && ch.clock !== null && ch.set_time != null) return { t: ch.set_time, end: null, approx: !!ch.set_approx };
  return null;
}

export function erasOf(cards: Card[], timeline: StoryChapter[]): Era[] {
  const chapters = new Map(timeline.map((c) => [c.id, c]));
  const out: Era[] = [];
  cards.forEach((c, i) => {
    if (c.kind !== "event" || !isType(c, "era")) return;
    const t = eventTime(c, chapters);
    if (!t) return;
    out.push({ id: c.id, name: c.name, colour: (c.era_colour as EraColour) ?? ERA_COLOURS[i % ERA_COLOURS.length]!, start: t.t, end: t.end, approx: t.approx, depth: 0 });
  });
  const within = (a: Era, b: Era) => a !== b && b.start <= a.start && (b.end === null || (a.end !== null && a.end <= b.end)) && !(a.start === b.start && a.end === b.end && a.id < b.id);
  for (const e of out) e.depth = out.filter((o) => within(e, o)).length;
  return out.sort((a, b) => a.start - b.start || a.depth - b.depth);
}

/** The era a time is in: the innermost holding it; between two overlapping without nesting, the later start. */
export function eraAt(t: number | null | undefined, eras: Era[]): Era | null {
  if (t == null) return null;
  let best: Era | null = null;
  for (const e of eras) {
    if (t < e.start || (e.end !== null && t > e.end)) continue;
    if (!best || e.depth > best.depth || (e.depth === best.depth && e.start > best.start)) best = e;
  }
  return best;
}

// ---- ages ------------------------------------------------------------------------------------------------------

const DEAD = /\b(dead|deceased|died|killed|slain|murdered)\b/i;

export interface LifeTime {
  t: number;
  approx: boolean;
}

/** The time a fact or a relationship starts on the axis: a time, or its chapter's set time. */
function startTime(x: { from: string | null; from_time?: number; from_approx?: boolean }, chapters: Map<string, StoryChapter>): LifeTime | null {
  if (x.from_time != null) return { t: x.from_time, approx: !!x.from_approx };
  const ch = x.from ? chapters.get(x.from) : undefined;
  if (ch && !ch.early && ch.clock !== null && ch.set_time != null) return { t: ch.set_time, approx: !!ch.set_approx };
  return null;
}

/** A character's birth: the start of their canon "born" fact, or the time of a birth event they are related to. */
export function birthOf(card: Card, byId: Map<string, Card>, chapters: Map<string, StoryChapter>): LifeTime | null {
  for (const f of card.facts) if (norm(f.label) === "born" && !f.outside_time) {
    const t = startTime(f, chapters);
    if (t) return t;
  }
  return lifeEvent(card, byId, chapters, "birth");
}

/** A character's death: the start of the "status" fact the Continuity check reads as dead, or a death event. */
export function deathOf(card: Card, byId: Map<string, Card>, chapters: Map<string, StoryChapter>): LifeTime | null {
  for (const f of card.facts) if (norm(f.label) === "status" && DEAD.test(f.value) && !f.outside_time) {
    const t = startTime(f, chapters);
    if (t) return t;
  }
  return lifeEvent(card, byId, chapters, "death");
}

function lifeEvent(card: Card, byId: Map<string, Card>, chapters: Map<string, StoryChapter>, kind: string): LifeTime | null {
  for (const r of card.relations) {
    if (r.other.kind !== "event" || r.standing !== "canon") continue;
    const ev = byId.get(r.other.id);
    if (!ev || !isType(ev, kind)) continue;
    const t = eventTime(ev, chapters);
    if (t) return { t: t.t, approx: t.approx };
  }
  return null;
}

/** "age 34", "about 34", "died at 61", "not born yet", or "" when it can't be worked out. */
export function ageText(birth: LifeTime | null, death: LifeTime | null, at: LifeTime | null, opts: { word?: boolean } = {}): string {
  if (!birth || !at) return "";
  if (at.t < birth.t) return "not born yet";
  const about = birth.approx || at.approx || (death?.approx ?? false) ? "about " : "";
  if (death && at.t > death.t) return `died at ${about}${Math.floor(death.t - birth.t)}`;
  const n = Math.floor(at.t - birth.t);
  return opts.word === false ? `${about}${n}` : `${about ? "about " : "age "}${n}`;
}

/** A character's age as of a chapter's place on the clock (its set time), for the name's card. */
export function ageAt(card: Card, place: number | undefined, indexOf: IndexOf, byId: Map<string, Card>, chapters: Map<string, StoryChapter>): string {
  if (card.kind !== "character" || place === undefined) return "";
  const t = indexOf.timeOf?.(place);
  if (t == null) return "";
  return ageText(birthOf(card, byId, chapters), deathOf(card, byId, chapters), { t, approx: false });
}

/** Does a span hold at a time (a fact or relationship, read with the clock)? */
export const holdsAt = (span: Parameters<typeof holds>[0], t: number, indexOf: IndexOf) => holds(span, { time: t }, indexOf);
