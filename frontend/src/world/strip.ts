// The mentions strip on an entry's page (docs/SPEC.md §12.1): one cell per current chapter in story order, filled by
// how often the chapter names the entry (three steps, by thirds of its own busiest chapter), a bar under the
// chapters told from its point of view, and the gaps: runs of chapters without it, between two that name it, once
// they reach the gap length of the project they start in. Worked out when shown, never stored.

import type { StoryChapter } from "../types";
import { atOrBefore, type At, type IndexOf } from "./time";

export interface StripCell {
  chapter: StoryChapter;
  /** its place in the story, from 1 */
  n: number;
  count: number;
  /** 0 for not named, else 1–3 */
  step: number;
  pov: boolean;
  /** later on the clock than the "as of" point (docs/SPEC.md §13.1.4) */
  later: boolean;
  asOf: boolean;
  /** uses of a name it shares that no choice line settles (docs/SPEC.md §14.10): a faint cell when it has no others */
  unsettled: number;
}

export interface Gap {
  /** story numbers (from 1) of the first and last chapter without the entry */
  from: number;
  to: number;
  length: number;
}

export interface Strip {
  rows: { project: string; name: string; cells: StripCell[] }[];
  gaps: Gap[];
  /** "In 31 of 48 chapters · first in 2 · …" */
  line: string;
}

const chapters = (n: number) => `${n} chapter${n === 1 ? "" : "s"}`;

/** Thirds of the busiest chapter: 1 for up to a third, 2 up to two thirds, 3 above. */
export function step(count: number, busiest: number): number {
  if (count <= 0 || busiest <= 0) return 0;
  return Math.min(3, Math.max(1, Math.ceil((3 * count) / busiest)));
}

export function mentionStrip(
  timeline: StoryChapter[],
  counts: Map<string, number>,
  entityId: string,
  asOf: At | null = null,
  indexOf?: IndexOf,
  unsettled: Map<string, number> = new Map(),
): Strip {
  // with no clock given, the strip's own book order is the clock (as before phase 12)
  const clock: IndexOf = indexOf ?? Object.assign((id: string | null) => timeline.find((c) => c.id === id)?.index, {});
  const busiest = Math.max(0, ...timeline.map((c) => counts.get(c.id) ?? 0));
  const cells: StripCell[] = timeline.map((c, i) => {
    const count = counts.get(c.id) ?? 0;
    const later = asOf !== null && !atOrBefore(c.id, asOf, clock);
    return { chapter: c, n: i + 1, count, step: step(count, busiest), pov: c.pov === entityId, later, asOf: asOf !== null && typeof asOf === "number" && clock(c.id) === asOf, unsettled: unsettled.get(c.id) ?? 0 };
  });
  const rows: Strip["rows"] = [];
  for (const cell of cells) {
    const last = rows[rows.length - 1];
    if (last?.project === cell.chapter.project) last.cells.push(cell);
    else rows.push({ project: cell.chapter.project, name: cell.chapter.project_name, cells: [cell] });
  }

  // runs without the entry between two that name it (they cross from one project into the next, as the story does)
  const named = cells.filter((c) => c.count > 0);
  const gaps: Gap[] = [];
  let longest: Gap | null = null;
  for (let i = 1; i < named.length; i++) {
    const from = named[i - 1]!.n + 1;
    const to = named[i]!.n - 1;
    const length = to - from + 1;
    if (length <= 0) continue;
    const gapLength = cells[from - 1]!.chapter.gap_chapters ?? 5;
    if (length >= gapLength) {
      const gap = { from, to, length };
      gaps.push(gap);
      if (!longest || length > longest.length) longest = gap;
    }
  }

  const parts: string[] = [];
  if (!named.length) parts.push(timeline.length ? `Not named in any of the ${chapters(timeline.length)} yet` : "No chapters yet");
  else {
    parts.push(`In ${named.length} of ${chapters(timeline.length)}`, `first in ${named[0]!.n}`, `last in ${named[named.length - 1]!.n}`);
    if (longest) parts.push(`longest gap: ${chapters(longest.length)} (${longest.from === longest.to ? longest.from : `${longest.from}–${longest.to}`})`);
    const after = timeline.length - named[named.length - 1]!.n;
    if (after > 0) parts.push(after === 1 ? "not named in the last chapter" : `not named in the last ${after}`);
  }
  // shared names no choice line settles count for nobody, and are said once (docs/SPEC.md §14.10)
  const vague = cells.filter((c) => c.unsettled > 0);
  if (vague.length) parts.push(`+ ${vague.reduce((k, c) => k + c.unsettled, 0)} unsettled in ${chapters(vague.length)}`);
  return { rows, gaps, line: parts.join(" · ") };
}
