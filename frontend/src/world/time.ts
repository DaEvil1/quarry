// Story time in the browser (docs/SPEC.md §13.1). The clock is happened order: chapters by the time they are set,
// then book order; `indexOf` gives a chapter's place on it (with `timeOf`, the time a place is set at). A fact or
// relationship holds from its start through its end, each a chapter or a time; a chapter with no set time ignores time
// bounds, and a chapter that left the book (retired) doesn't bound anything. Among facts with the same label, the one
// that started latest wins: "status: dead from chapter 9" takes over from "status: alive" there, without "alive"
// needing an end. Outside time is never on the clock: such a fact always holds, beside whatever holds in time.

import type { Span } from "../types";

/** "As of": a chapter's place on the clock, a time ("as of year 0"), or a chapter outside time. */
export type At = number | { time: number } | { outside: true };

/** A chapter id → its place on the clock (undefined for one not on it); `timeOf` gives the set time of a place. */
export type IndexOf = ((chapterId: string | null) => number | undefined) & { timeOf?: (place: number) => number | null | undefined };

const isTime = (at: At): at is { time: number } => typeof at === "object" && "time" in at;
const isOutside = (at: At): at is { outside: true } => typeof at === "object" && "outside" in at;
const bounded = (s: Span) => !!(s.from_chapter_id || s.until_chapter_id || s.from_time != null || s.until_time != null);

/** Does a span hold at a point on the clock? */
export function holds(span: Span, at: At, indexOf: IndexOf): boolean {
  if (span.outside_time) return true;
  if (isOutside(at)) return !bounded(span);
  const from = indexOf(span.from_chapter_id);
  const until = indexOf(span.until_chapter_id);
  if (isTime(at)) {
    // as of a time: chapter bounds compare by their set time, and chapters set at that time count as begun
    const tf = from === undefined ? null : (indexOf.timeOf?.(from) ?? null);
    const tu = until === undefined ? null : (indexOf.timeOf?.(until) ?? null);
    if (tf !== null && tf > at.time) return false;
    if (tu !== null && at.time > tu) return false;
    if (span.from_time != null && span.from_time > at.time) return false;
    if (span.until_time != null && at.time > span.until_time) return false;
    return true;
  }
  if (from !== undefined && from > at) return false;
  if (until !== undefined && at > until) return false;
  const t = indexOf.timeOf?.(at);
  if (t != null) {
    if (span.from_time != null && t < span.from_time) return false;
    if (span.until_time != null && t > span.until_time) return false;
  }
  return true;
}

/** Which of two starts is later on the clock (>0 when `a` is): a from-time sits just before the chapters set at it. */
export function startCmp(a: Span, b: Span, indexOf: IndexOf): number {
  const key = (s: Span): { place?: number; time?: number | null } | null => {
    if (s.from_time != null) return { time: s.from_time };
    const p = indexOf(s.from_chapter_id);
    return p === undefined ? null : { place: p, time: indexOf.timeOf?.(p) ?? null };
  };
  const x = key(a);
  const y = key(b);
  if (!x || !y) return (x ? 1 : 0) - (y ? 1 : 0);
  if (x.place !== undefined && y.place !== undefined) return x.place - y.place;
  if (x.place === undefined && y.place === undefined) return (x.time ?? 0) - (y.time ?? 0);
  // a chapter against a time: a chapter set at (or after) the time is later; one with no set time is earlier
  const [chapter, time, sign] = x.place !== undefined ? [x, y, 1] : [y, x, -1];
  if (chapter.time == null) return -sign;
  return (chapter.time >= (time.time ?? 0) ? 1 : -1) * sign;
}

/** A label or value as it is compared: whatever the capitals, spaces trimmed (docs/SPEC.md §12.6). */
export const norm = (text: string) => text.trim().replace(/\s+/g, " ").toLowerCase();

/** The facts true at a point: those whose span holds, the latest-starting one per label. A label that holds several
 * values at once (`several`) keeps every value whose span holds. Outside time is always kept, after the one in time,
 * and neither takes over from the other. */
export function factsAsOf<F extends Span & { label: string }>(facts: F[], at: At, indexOf: IndexOf, several?: (label: string) => boolean): F[] {
  const best = new Map<string, F>();
  const keep = new Set<F>();
  const outside: F[] = [];
  for (const f of facts) {
    if (f.outside_time) {
      outside.push(f);
      continue;
    }
    if (!holds(f, at, indexOf)) continue;
    if (several?.(f.label)) {
      keep.add(f);
      continue;
    }
    const key = norm(f.label);
    const prev = best.get(key);
    if (!prev || startCmp(f, prev, indexOf) >= 0) best.set(key, f);
  }
  for (const f of best.values()) keep.add(f);
  return [...facts.filter((f) => keep.has(f)), ...outside];
}

/** How a time reads: a number in the world's unit (`year 312`, `years 300–302`, `about year −800`). */
export type TimeFormat = (time: number, approx?: boolean) => string;
export const numberText = (n: number) => (Number.isInteger(n) ? String(n) : String(Number(n.toFixed(6)))).replace("-", "−");
export const yearFormat: TimeFormat = (t, approx) => `${approx ? "about " : ""}year ${numberText(t)}`;

/** "from Storm", "until year 0", "Arrival – Storm", "outside time", or "" for always. */
export function spanText(span: Span, title: (id: string) => string | undefined, fmt: TimeFormat = yearFormat): string {
  if (span.outside_time) return "outside time";
  const from = span.from_time != null ? fmt(span.from_time, span.from_approx) : span.from_chapter_id ? (title(span.from_chapter_id) ?? "a removed chapter") : null;
  const until = span.until_time != null ? fmt(span.until_time, span.until_approx) : span.until_chapter_id ? (title(span.until_chapter_id) ?? "a removed chapter") : null;
  if (from && until) return from === until ? `in ${from}` : `${from} – ${until}`;
  if (from) return `from ${from}`;
  if (until) return `until ${until}`;
  return "";
}

/** Is a chapter at or before a point on the clock (begun as of it)? A chapter not on the clock (outside time) never
 * counts as later. */
export function atOrBefore(chapterId: string, at: At, indexOf: IndexOf): boolean {
  const p = indexOf(chapterId);
  if (p === undefined || isOutside(at)) return true;
  if (isTime(at)) {
    const t = indexOf.timeOf?.(p);
    return t == null || t <= at.time;
  }
  return p <= at;
}
