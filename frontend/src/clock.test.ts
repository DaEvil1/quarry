import { describe, expect, it } from "vitest";

import type { StoryChapter } from "./types";
import { asIfAccepted } from "./world/asif";
import { mentionStrip } from "./world/strip";
import { atOrBefore, factsAsOf, holds, spanText, startCmp, type IndexOf } from "./world/time";
import { asOfLabel, chapterWhen, parseTime, timeText } from "./world/when";

// Phase 12a (docs/SPEC.md §13.1): the clock in the browser. Chapters 1–13 are set in year 312, chapter 14 is a tale in
// year −800 (first on the clock), 15 carries on in 312; places on the clock: 14 → 0, 1..13 → 1..13, 15 → 14.
const book = Array.from({ length: 15 }, (_, i) => `c${i + 1}`);
const place = new Map(book.map((id, i) => [id, i === 13 ? 0 : i === 14 ? 14 : i + 1]));
const time = new Map([...place.values()].map((p) => [p, p === 0 ? -800 : 312]));
const indexOf = Object.assign((id: string | null) => (id ? place.get(id) : undefined), { timeOf: (p: number) => time.get(p) }) as IndexOf;
const at = (id: string) => place.get(id)!;
const f = (label: string, value: string, extra: Record<string, unknown> = {}) => ({ label, value, from_chapter_id: null, until_chapter_id: null, ...extra });
const u = { unit: "year", units: "years" };

describe("the clock", () => {
  it("dead from chapter 9 holds in 10 and 15, not in the tale (14) set before it", () => {
    const facts = [f("status", "alive"), f("status", "dead", { from_chapter_id: "c9" })];
    expect(factsAsOf(facts, at("c14"), indexOf).map((x) => x.value)).toEqual(["alive"]);
    expect(factsAsOf(facts, at("c15"), indexOf).map((x) => x.value)).toEqual(["dead"]);
    expect(factsAsOf(facts, at("c8"), indexOf).map((x) => x.value)).toEqual(["alive"]);
  });

  it("time bounds: born from year 278 holds as of year 312 and not as of year 0", () => {
    const born = f("born", "", { from_time: 278 });
    expect(holds(born, at("c1"), indexOf)).toBe(true);
    expect(holds(born, at("c14"), indexOf)).toBe(false);
    expect(holds(born, { time: 0 }, indexOf)).toBe(false);
    expect(holds(born, { time: 278 }, indexOf)).toBe(true);
    // a chapter bound read as of a time compares by its set time; chapters set at that time count as begun
    expect(holds(f("x", "y", { from_chapter_id: "c9" }), { time: 312 }, indexOf)).toBe(true);
    expect(holds(f("x", "y", { from_chapter_id: "c9" }), { time: 0 }, indexOf)).toBe(false);
    // a chapter with no set time ignores time bounds
    const plain = Object.assign((id: string | null) => (id ? book.indexOf(id) : undefined), {}) as IndexOf;
    expect(holds(born, 3, plain)).toBe(true);
  });

  it("a from-time sits just before the chapters set at it", () => {
    const a = f("title", "A", { from_time: 312 });
    const b = f("title", "B", { from_chapter_id: "c3" });
    expect(startCmp(b, a, indexOf)).toBeGreaterThan(0);
    expect(factsAsOf([b, a], at("c5"), indexOf).map((x) => x.value)).toEqual(["B"]);
  });

  it("outside time is always shown, after the value in time, and never takes over", () => {
    const facts = [f("title", "Queen of the Hollow Court", { outside_time: true }), f("title", "Lady of Old Harbour")];
    expect(factsAsOf(facts, at("c2"), indexOf).map((x) => x.value)).toEqual(["Lady of Old Harbour", "Queen of the Hollow Court"]);
    expect(factsAsOf(facts, { time: 0 }, indexOf).map((x) => x.value)).toEqual(["Lady of Old Harbour", "Queen of the Hollow Court"]);
    // as of a chapter outside time: what changes over time isn't shown
    const bounded = [f("status", "dead", { from_chapter_id: "c9" }), f("eyes", "grey"), facts[0]!];
    expect(factsAsOf(bounded, { outside: true }, indexOf).map((x) => x.value)).toEqual(["grey", "Queen of the Hollow Court"]);
  });

  it("dims what is later on the clock, not in the book", () => {
    expect(atOrBefore("c14", at("c2"), indexOf)).toBe(true);
    expect(atOrBefore("c3", at("c2"), indexOf)).toBe(false);
    const timeline = book.map((id, i) => ({ id, title: id, project: "p", project_name: "P", index: i })) as StoryChapter[];
    const strip = mentionStrip(timeline, new Map(), "x", at("c2"), indexOf);
    expect(strip.rows[0]!.cells.filter((c) => c.later).map((c) => c.chapter.id)).toEqual(book.slice(2, 13).concat("c15"));
  });

  it("reads spans and times", () => {
    const title = (id: string) => ({ c9: "The Storm" })[id];
    expect(spanText(f("x", "y", { from_time: 278 }), title)).toBe("from year 278");
    expect(spanText(f("x", "y", { from_time: 0, until_chapter_id: "c9" }), title)).toBe("year 0 – The Storm");
    expect(spanText(f("x", "y", { from_time: -800, from_approx: true, until_time: 0 }), title)).toBe("about year −800 – year 0");
    expect(spanText(f("x", "y", { outside_time: true }), title)).toBe("outside time");
    expect(timeText({ time_at: 312 }, u)).toBe("year 312");
    expect(timeText({ time_at: 300, time_end: 302 }, u)).toBe("years 300–302");
    expect(timeText({ time_at: -800, time_approx: true }, u)).toBe("about year −800");
    expect(timeText({ time_at: -800, time_label: "800 years before the Founding" }, u)).toBe("800 years before the Founding");
    expect(timeText({ time_at: null, outside_time: true }, u)).toBe("outside time");
    expect(timeText({ time_at: 3 }, { unit: "day", units: "days" })).toBe("day 3");
    expect(parseTime("−800")).toBe(-800);
    expect(parseTime("312.5")).toBe(312.5);
    expect(parseTime("soon")).toBe(null);
    const tale = { id: "c14", title: "The Drowned Bell", project: "p", project_name: "P", index: 13, time_at: -800, told_as: "tale" } as StoryChapter;
    expect(asOfLabel(tale, 14, u)).toBe("14 · The Drowned Bell — tale, year −800");
    expect(chapterWhen({ ...tale, time_at: null, set_time: 312 } as StoryChapter, u)).toEqual({ text: "year 312", own: false });
  });
});

describe("read as if accepted", () => {
  const ch = (id: string, position: number, extra: Record<string, unknown> = {}) => ({ id, state: "current" as const, position, project: "p", experiment_item_id: null, ...extra });
  const exp = { id: "x", range: [{ id: "c2" }, { id: "c3" }], insert: null };
  it("puts the drafts in place of the range", () => {
    const chapters = [ch("c1", 0), ch("c2", 1), ch("c3", 2), ch("c4", 3), ch("d1", 0, { state: "experiment", experiment_item_id: "x", experiment: exp }), ch("d2", 1, { state: "experiment", experiment_item_id: "x", experiment: exp })];
    expect(asIfAccepted(chapters, "p", "x").map((c) => c.id)).toEqual(["c1", "d1", "d2", "c4"]);
    expect(asIfAccepted(chapters, "p", null).map((c) => c.id)).toEqual(["c1", "c2", "c3", "c4"]);
  });
  it("or at the place an experiment adds at", () => {
    const add = { id: "y", range: [], insert: { chapter_id: "c1", side: "before" as const } };
    const chapters = [ch("c1", 0), ch("c2", 1), ch("p1", 0, { state: "experiment", experiment_item_id: "y", experiment: add })];
    expect(asIfAccepted(chapters, "p", "y").map((c) => c.id)).toEqual(["p1", "c1", "c2"]);
  });
});
