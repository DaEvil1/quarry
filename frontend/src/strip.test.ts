import { describe, expect, it } from "vitest";

import type { StoryChapter } from "./types";
import { mentionStrip, step } from "./world/strip";

// Phase 11 §12.1: the mentions strip on an entry's page.
const book = (n: number, project = "nine", gap = 5, pov: Record<number, string> = {}): StoryChapter[] =>
  Array.from({ length: n }, (_, i) => ({ id: `${project}-${i + 1}`, title: `Chapter ${i + 1}`, project, project_name: project === "nine" ? "Ninefold" : "The Salt Road", index: i, pov: pov[i + 1] ?? null, gap_chapters: gap }));

describe("the mentions strip", () => {
  it("done when: Isolde named in 1–3 and 14–20 of 20 has a 10-chapter gap, her POV chapters marked, as of 10 dims 11–20", () => {
    const timeline = book(20, "nine", 5, { 2: "isolde", 15: "isolde", 16: "varren" });
    const counts = new Map<string, number>();
    for (const n of [1, 2, 3, 14, 15, 16, 17, 18, 19, 20]) counts.set(`nine-${n}`, n === 15 ? 9 : 2);
    const s = mentionStrip(timeline, counts, "isolde");
    const cells = s.rows[0]!.cells;
    expect(cells.filter((c) => c.count > 0).map((c) => c.n)).toEqual([1, 2, 3, 14, 15, 16, 17, 18, 19, 20]);
    expect(s.gaps).toEqual([{ from: 4, to: 13, length: 10 }]);
    expect(s.line).toBe("In 10 of 20 chapters · first in 1 · last in 20 · longest gap: 10 chapters (4–13)");
    expect(cells.filter((c) => c.pov).map((c) => c.n)).toEqual([2, 15]);
    // shaded by thirds of her own busiest chapter (9): 2 is the lightest step
    expect(cells[0]!.step).toBe(1);
    expect(cells[14]!.step).toBe(3);

    const asOf = mentionStrip(timeline, counts, "isolde", 9);
    expect(asOf.rows[0]!.cells.filter((c) => c.later).map((c) => c.n)).toEqual([11, 12, 13, 14, 15, 16, 17, 18, 19, 20]);
    expect(asOf.rows[0]!.cells.find((c) => c.asOf)!.n).toBe(10);
  });

  it("three steps by thirds of the busiest chapter", () => {
    expect([0, 1, 3, 4, 6, 7, 9].map((n) => step(n, 9))).toEqual([0, 1, 1, 2, 2, 3, 3]);
    expect(step(1, 1)).toBe(3);
  });

  it("a run shorter than the gap length isn't a gap; the line says when the last chapters don't name it", () => {
    const timeline = book(10);
    const counts = new Map([["nine-1", 1], ["nine-4", 1], ["nine-7", 1]]);
    const s = mentionStrip(timeline, counts, "x");
    expect(s.gaps).toEqual([]);
    expect(s.line).toBe("In 3 of 10 chapters · first in 1 · last in 7 · not named in the last 3");
    expect(mentionStrip(timeline, new Map(), "x").line).toBe("Not named in any of the 10 chapters yet");
  });

  it("each project is its own row, and a gap crossing into the next book uses the length of the one it starts in", () => {
    const timeline = [...book(4, "nine", 3), ...book(4, "salt", 10)].map((c, i) => ({ ...c, index: i }));
    const counts = new Map([["nine-1", 1], ["salt-4", 1]]);
    const s = mentionStrip(timeline, counts, "x");
    expect(s.rows.map((r) => [r.name, r.cells.length])).toEqual([["Ninefold", 4], ["The Salt Road", 4]]);
    // six chapters without, starting in Ninefold (gap length 3)
    expect(s.gaps).toEqual([{ from: 2, to: 7, length: 6 }]);
    // starting in The Salt Road (gap length 10), the same run isn't one
    const later = mentionStrip(timeline, new Map([["nine-4", 1], ["salt-4", 1]]), "x");
    expect(later.gaps).toEqual([]);
  });
});
