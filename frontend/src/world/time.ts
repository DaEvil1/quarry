// Story time in the browser: chapters are the clock. A fact or relationship holds from its first chapter through its
// last (either may be open). Among facts with the same label, the one that started latest wins: "status: dead from
// chapter 9" takes over from "status: alive" there, without "alive" needing an end.

import type { Span } from "../types";

export type IndexOf = (chapterId: string | null) => number | undefined;

/** Does a span hold at chapter index `at`? A chapter no longer in the story (retired) doesn't bound it. */
export function holds(span: Span, at: number, indexOf: IndexOf): boolean {
  const from = indexOf(span.from_chapter_id);
  const until = indexOf(span.until_chapter_id);
  return (from === undefined || from <= at) && (until === undefined || at <= until);
}

/** The facts true at chapter index `at`: those whose span holds, the latest-starting one per label. */
export function factsAsOf<F extends Span & { label: string }>(facts: F[], at: number, indexOf: IndexOf): F[] {
  const best = new Map<string, F>();
  for (const f of facts) {
    if (!holds(f, at, indexOf)) continue;
    const key = f.label.toLowerCase();
    const prev = best.get(key);
    if (!prev || (indexOf(f.from_chapter_id) ?? -1) >= (indexOf(prev.from_chapter_id) ?? -1)) best.set(key, f);
  }
  const keep = new Set(best.values());
  return facts.filter((f) => keep.has(f));
}

/** "from Storm", "until Arrival", "Arrival – Storm", or "" for always. */
export function spanText(span: Span, title: (id: string) => string | undefined): string {
  const from = span.from_chapter_id ? (title(span.from_chapter_id) ?? "a removed chapter") : null;
  const until = span.until_chapter_id ? (title(span.until_chapter_id) ?? "a removed chapter") : null;
  if (from && until) return from === until ? `in ${from}` : `${from} – ${until}`;
  if (from) return `from ${from}`;
  if (until) return `until ${until}`;
  return "";
}
