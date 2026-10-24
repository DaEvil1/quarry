// Word history (docs/SPEC.md §11.5): words written and cut per day, worked out from the words each revision added and
// removed (kept with it on the server), summed here in the browser's own time zone. No streaks, goals or judging:
// a day without writing is simply an empty bar.

import type { WordHistory } from "./manuscript";

export type Range = "weeks" | "year" | "all";

export const RANGES: { value: Range; label: string }[] = [
  { value: "weeks", label: "8 weeks" },
  { value: "year", label: "a year" },
  { value: "all", label: "all" },
];

export interface Bar {
  key: string;
  /** what hovering it says: the day, the week or the month */
  label: string;
  written: number;
  cut: number;
  /** titles of the chapters touched */
  chapters: string[];
}

const pad = (n: number) => String(n).padStart(2, "0");
const dayKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
/** weeks start on Monday */
const startOfWeek = (d: Date) => {
  const s = startOfDay(d);
  s.setDate(s.getDate() - ((s.getDay() + 6) % 7));
  return s;
};
const monthKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;

const dayFmt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const shortFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const monthFmt = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });

/** The bars for a range, oldest first, ending at `now`, with the range's totals. */
export function wordBars(h: WordHistory, range: Range, now = new Date()): { bars: Bar[]; written: number; cut: number } {
  const slots: { key: string; label: string; start: Date }[] = [];
  let keyOf: (d: Date) => string;
  if (range === "weeks") {
    keyOf = dayKey;
    const today = startOfDay(now);
    for (let i = 55; i >= 0; i--) {
      const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
      slots.push({ key: dayKey(d), label: dayFmt.format(d), start: d });
    }
  } else if (range === "year") {
    keyOf = (d) => dayKey(startOfWeek(d));
    const week = startOfWeek(now);
    for (let i = 51; i >= 0; i--) {
      const d = new Date(week.getFullYear(), week.getMonth(), week.getDate() - 7 * i);
      slots.push({ key: dayKey(d), label: `week of ${shortFmt.format(d)}`, start: d });
    }
  } else {
    keyOf = monthKey;
    const times = h.revisions.map((r) => new Date(r.at).getTime());
    const first = new Date(Math.min(now.getTime(), ...times));
    for (let d = new Date(first.getFullYear(), first.getMonth(), 1); d <= now; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
      slots.push({ key: monthKey(d), label: monthFmt.format(d), start: d });
    }
  }
  const by = new Map(slots.map((s) => [s.key, { key: s.key, label: s.label, written: 0, cut: 0, touched: new Set<string>() }]));
  const add = (at: Date, chapter: string, added: number, removed: number) => {
    const bar = by.get(keyOf(at));
    if (!bar) return;
    bar.written += added;
    bar.cut += removed;
    bar.touched.add(chapter);
  };
  for (const r of h.revisions) add(new Date(r.at), r.chapter_id, r.added, r.removed);
  for (const p of h.pending) add(now, p.chapter_id, p.added, p.removed);
  const bars = [...by.values()].map(({ touched, ...b }) => ({
    ...b,
    chapters: [...touched].map((id) => h.chapters[id] ?? "a chapter").sort((a, b) => a.localeCompare(b)),
  }));
  return { bars, written: bars.reduce((n, b) => n + b.written, 0), cut: bars.reduce((n, b) => n + b.cut, 0) };
}
