// "Do these share a chapter?" on the Where-everyone-is grid (docs/SPEC.md §12.3), worked out in the browser from the
// grid's cells: which chapters to show for the rows ticked, and a line saying what was found. "Named in the same
// chapter" is all it claims.

import type { WhereGrid, WhereRow } from "../types";

export type Share = "all" | "any" | "every";

const named = (row: WhereRow, chapterId: string) => (row.cells[chapterId]?.count ?? 0) > 0;

/** "Varren, Isolde and the logbook" */
export function listNames(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export function shareFilter(grid: WhereGrid, rows: WhereRow[], ticked: Set<string>, share: Share): { chapters: string[]; line: string } {
  const all = grid.chapters.map((c) => c.id);
  const chosen = ticked.size ? rows.filter((r) => ticked.has(r.entity.id)) : rows;
  if (share === "all" || !chosen.length) return { chapters: all, line: "" };
  const keep = all.filter((id) => (share === "any" ? chosen.some((r) => named(r, id)) : chosen.every((r) => named(r, id))));
  const who = listNames(chosen.map((r) => r.entity.name));
  if (share === "any") return { chapters: keep, line: `${who} ${chosen.length === 1 ? "is" : "are"} named in ${keep.length} of ${all.length} chapters` };
  if (chosen.length < 2) return { chapters: keep, line: `${who} is named in ${keep.length} of ${all.length} chapters` };
  if (keep.length) return { chapters: keep, line: `${who} are named together in ${keep.length} of ${all.length} chapters` };
  // never together: with two ticked, the nearest miss
  if (chosen.length === 2) {
    const [a, b] = chosen as [WhereRow, WhereRow];
    const at = (r: WhereRow) => all.map((id, i) => (named(r, id) ? i : -1)).filter((i) => i >= 0);
    let best: [number, number] | null = null;
    for (const i of at(a)) for (const j of at(b)) if (!best || Math.abs(i - j) < Math.abs(best[0] - best[1])) best = [i, j];
    if (best) return { chapters: keep, line: `Never in the same chapter. Closest: ${a.entity.name} in ${best[0] + 1}, ${b.entity.name} in ${best[1] + 1}.` };
  }
  return { chapters: keep, line: `${who} are never named in the same chapter` };
}

/** How strongly a cell is shaded: by thirds of the row's own busiest chapter (as on the mentions strip). */
export function rowSteps(row: WhereRow): Map<string, number> {
  const busiest = Math.max(0, ...Object.values(row.cells).map((c) => c.count));
  return new Map(Object.entries(row.cells).map(([id, c]) => [id, c.count && busiest ? Math.min(3, Math.ceil((3 * c.count) / busiest)) : 0]));
}
