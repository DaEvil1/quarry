// Labels and values (docs/SPEC.md §12.6), worked out in the browser from the cards: each entry's values for a label
// as they stand at the end of the story, filtering and grouping a kind's table by them, and which expected labels an
// entry is missing. Labels and values match whatever the capitals; a value is shown in its most-used spelling.

import type { Card } from "./cards";
import { factsAsOf, norm, type IndexOf } from "./time";

export { norm };

/** An entry's values for a label at the end of the story (the latest that holds, or all that hold for a label with
 * several values), in their own spelling. */
export function valuesAtEnd(card: Card, label: string, several: boolean, last: number | null, indexOf: IndexOf): string[] {
  const key = norm(label);
  const facts = card.facts.filter((f) => norm(f.label) === key).map((f) => ({ ...f, from_chapter_id: f.from, until_chapter_id: f.until }));
  const held = last === null ? facts : factsAsOf(facts, last, indexOf, () => several);
  // with no chapters, or nothing that holds at the end: the latest recorded
  const pick = held.length ? held : facts.slice(-1);
  const out: string[] = [];
  for (const f of several ? pick : pick.slice(-1)) if (f.value.trim() && !out.some((v) => norm(v) === norm(f.value))) out.push(f.value.trim());
  return out;
}

export interface ValueFilter {
  label: string;
  value: string;
}

/** "type:Festival" in the address, and back. */
export const filterText = (f: ValueFilter) => `${f.label}:${f.value}`;
export function parseFilter(text: string): ValueFilter | null {
  const at = text.indexOf(":");
  if (at <= 0) return null;
  return { label: text.slice(0, at), value: text.slice(at + 1) };
}

export interface LabelReader {
  several: (kind: string, label: string) => boolean;
  last: number | null;
  indexOf: IndexOf;
}

/** Entries that have every filter's value (a label with several values matches any of them). */
export function matches(card: Card, filters: ValueFilter[], r: LabelReader): boolean {
  return filters.every((f) => valuesAtEnd(card, f.label, r.several(card.kind, f.label), r.last, r.indexOf).some((v) => norm(v) === norm(f.value)));
}

export interface Group<T> {
  /** the value in its most-used spelling, or null for "no …" */
  value: string | null;
  items: T[];
}

/** One group per value, in order of size, and the entries without the label last. An entry with several values is in
 * each of their groups. */
export function groupBy<T>(items: T[], card: (item: T) => Card | undefined, label: string, r: LabelReader): Group<T>[] {
  const groups = new Map<string, { spellings: Map<string, number>; items: T[] }>();
  const none: T[] = [];
  for (const item of items) {
    const c = card(item);
    const values = c ? valuesAtEnd(c, label, r.several(c.kind, label), r.last, r.indexOf) : [];
    if (!values.length) none.push(item);
    for (const v of values) {
      const g = groups.get(norm(v)) ?? { spellings: new Map<string, number>(), items: [] as T[] };
      g.spellings.set(v, (g.spellings.get(v) ?? 0) + 1);
      g.items.push(item);
      groups.set(norm(v), g);
    }
  }
  const out: Group<T>[] = [...groups.values()]
    .map((g) => ({ value: [...g.spellings].sort((a, b) => b[1] - a[1])[0]![0], items: g.items }))
    .sort((a, b) => b.items.length - a.items.length || a.value!.localeCompare(b.value!));
  if (none.length) out.push({ value: null, items: none });
  return out;
}

/** The labels a kind's entries use, by how many entries have them, each in its most-used spelling. */
export function labelsOfKind(cards: Card[], kind: string): { label: string; count: number }[] {
  const seen = new Map<string, { spellings: Map<string, number>; entries: Set<string> }>();
  for (const c of cards) {
    if (c.kind !== kind) continue;
    for (const f of c.facts) {
      const s = seen.get(norm(f.label)) ?? { spellings: new Map(), entries: new Set() };
      s.spellings.set(f.label, (s.spellings.get(f.label) ?? 0) + 1);
      s.entries.add(c.id);
      seen.set(norm(f.label), s);
    }
  }
  return [...seen.values()]
    .map((s) => ({ label: [...s.spellings].sort((a, b) => b[1] - a[1])[0]![0], count: s.entries.size }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

/** The expected labels an entry doesn't have (any standing counts as having it). */
export function missingLabels(card: Card, expected: string[]): string[] {
  const has = new Set(card.labels ?? card.facts.map((f) => norm(f.label)));
  return expected.filter((l) => !has.has(norm(l)));
}

/** The resolution key of a missing-label finding: entry and label. */
export const missingKey = (entityId: string, label: string) => `${entityId}:${norm(label)}`;

/** A fact labelled "pronunciation" is shown after the name, not among the facts. */
export const isPronunciation = (label: string) => norm(label) === "pronunciation";
