import { describe, expect, it } from "vitest";

import type { WhereGrid, WhereRow } from "./types";
import { listNames, rowSteps, shareFilter } from "./world/where";

// Phase 11 §12.3: "Do these share a chapter?" on the grid of entries across chapters.
const chapters = Array.from({ length: 20 }, (_, i) => ({ id: `c${i + 1}`, title: `Chapter ${i + 1}`, project: "nine", project_name: "Ninefold", pov: null }));
const row = (name: string, kind: WhereRow["entity"]["kind"], named: number[], counts: Record<number, number> = {}): WhereRow => ({
  entity: { id: name, name, kind },
  added: true,
  cells: Object.fromEntries(named.map((n) => [`c${n}`, { count: counts[n] ?? 1, recorded: null, note: null, derived: null, present: true, people: [] }])),
});
const grid = (rows: WhereRow[]): WhereGrid => ({ chapters, rows, events: {} });

describe("do these share a chapter?", () => {
  const varren = row("Varren", "character", [1, 2, 5, 9, 14]);
  const isolde = row("Isolde", "character", [2, 5, 9, 12, 20]);
  const logbook = row("the logbook", "object", [2, 5, 9, 13, 14], { 9: 6 });
  const guild = row("the Lamp Guild", "faction", [3]);
  const g = grid([varren, isolde, logbook, guild]);

  it("done when: ticking Varren and the logbook with all of them leaves only the chapters naming both, and says how many", () => {
    const f = shareFilter(g, g.rows, new Set(["Varren", "the logbook"]), "every");
    expect(f.chapters).toEqual(["c2", "c5", "c9", "c14"]);
    expect(f.line).toBe("Varren and the logbook are named together in 4 of 20 chapters");
    const three = shareFilter(g, g.rows, new Set(["Varren", "Isolde", "the logbook"]), "every");
    expect(three.line).toBe("Varren, Isolde and the logbook are named together in 3 of 20 chapters");
  });

  it("any of them, all chapters, and nothing ticked applies to every row", () => {
    expect(shareFilter(g, g.rows, new Set(["the Lamp Guild", "Isolde"]), "any").chapters).toEqual(["c2", "c3", "c5", "c9", "c12", "c20"]);
    expect(shareFilter(g, g.rows, new Set(["Varren"]), "all").chapters).toHaveLength(20);
    expect(shareFilter(g, g.rows, new Set(), "every").chapters).toEqual([]);
    expect(shareFilter(g, [varren, isolde], new Set(), "every").chapters).toEqual(["c2", "c5", "c9"]);
  });

  it("two never together: the nearest miss", () => {
    const a = row("Isolde", "character", [1, 12]);
    const b = row("the logbook", "object", [13, 20]);
    const f = shareFilter(grid([a, b]), [a, b], new Set(["Isolde", "the logbook"]), "every");
    expect(f.chapters).toEqual([]);
    expect(f.line).toBe("Never in the same chapter. Closest: Isolde in 12, the logbook in 13.");
  });

  it("cells are shaded by thirds of the row's busiest chapter", () => {
    expect(rowSteps(logbook).get("c9")).toBe(3);
    expect(rowSteps(logbook).get("c2")).toBe(1);
    expect(listNames(["a"])).toBe("a");
  });
});
