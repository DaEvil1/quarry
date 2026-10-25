// In-world time in words (docs/SPEC.md §13.1.1): a number in the world's unit (`year 312`, `years 300–302`), a free
// label when there is one, `about …` for an approximate time, and `outside time`. No calendar: numbers are never
// converted, split into months or worked out into weekdays.

import type { StoryChapter, TimeValue, World } from "../types";
import { numberText, type TimeFormat } from "./time";

export interface Unit {
  unit: string;
  units: string;
}

export const unitOf = (world?: Pick<World, "time_unit" | "time_units"> | null): Unit => ({
  unit: world?.time_unit || "year",
  units: world?.time_units || "years",
});

/** A single time: "year 312", "about year −800". */
export const timeFormat = (u: Unit): TimeFormat => (t, approx) => `${approx ? "about " : ""}${u.unit} ${numberText(t)}`;

/** A chapter's or an event's time as shown: its label (the number small beside it is the caller's), the number with
 * the unit, a span, "about", or "outside time"; "" when not set. */
export function timeText(v: Partial<TimeValue> | null | undefined, u: Unit, opts: { label?: boolean } = {}): string {
  if (!v) return "";
  if (v.outside_time) return "outside time";
  if (v.time_at == null) return "";
  if (v.time_label && opts.label !== false) return v.time_label;
  const n = v.time_end != null && v.time_end !== v.time_at ? `${u.units} ${numberText(v.time_at)}–${numberText(v.time_end)}` : `${u.unit} ${numberText(v.time_at)}`;
  return v.time_approx ? `about ${n}` : n;
}

/** The number behind a labelled time, small beside the label: "year 312". */
export const numberOf = (v: Partial<TimeValue>, u: Unit) => (v.time_label ? timeText({ ...v, time_label: null }, u) : "");

/** When a chapter is set, in words: its own time, or the time it carries on from (`set_time`), or a mark's "before
 * the story", or "". */
export function chapterWhen(c: StoryChapter, u: Unit): { text: string; own: boolean } {
  if (c.outside_time) return { text: "outside time", own: true };
  if (c.time_at != null) return { text: timeText(c, u), own: true };
  if (c.early) return { text: "before the story", own: false };
  if (c.set_time != null) return { text: timeText({ time_at: c.set_time, time_approx: c.set_approx }, u), own: false };
  return { text: "", own: false };
}

/** "14 · The Drowned Bell — tale, year −800": a chapter in the "as of" selector (docs/SPEC.md §13.1.6). */
export function asOfLabel(c: StoryChapter, n: number, u: Unit): string {
  const when = c.outside_time ? "outside time" : c.time_at != null ? timeText(c, u) : "";
  const parts = [c.told_as ?? "", when].filter(Boolean).join(", ");
  return `${n} · ${c.title}${parts ? ` — ${parts}` : ""}`;
}

/** Parse a typed time: "312", "-800", "−800", "312.5"; null for anything else. */
export function parseTime(text: string): number | null {
  const t = text.trim().replace("−", "-").replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(t)) return null;
  return Number(t);
}
