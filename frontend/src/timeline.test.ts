import { describe, expect, it } from "vitest";

import type { Chronology } from "./history";
import type { StoryChapter } from "./types";
import type { Card } from "./world/cards";
import { ageText, birthOf, deathOf, eraAt, erasOf } from "./world/eras";
import { entitySlice } from "./world/slice";
import { breakdown, buildLanes, buildModel, cluster, fitScale, FOLD_W, inSpan, makeAxis, placeLabels, scaleOfStep, stepOf, ticks } from "./world/timeline";

// Phase 12b (docs/SPEC.md §13.2): eras, ages, the Timeline's model, lanes, its axis with folds, clusters, and an
// entry's own slice, worked out in the browser. The book: chapters 1–13 in year 312, 14 a tale in year −800.
const u = { unit: "year", units: "years" };
const timeline: StoryChapter[] = Array.from({ length: 15 }, (_, i) => ({
  id: `c${i + 1}`,
  title: i === 13 ? "The Drowned Bell" : `Chapter ${i + 1}`,
  project: "p",
  project_name: "Lamps",
  index: i,
  told_as: i === 13 ? "tale" : null,
  time_at: i === 13 ? -800 : i < 13 ? 312 : null,
  set_time: i === 13 ? -800 : 312,
  clock: i === 13 ? 0 : i === 14 ? 14 : i + 1,
}));
const chapters = new Map(timeline.map((c) => [c.id, c]));

const card = (id: string, kind: Card["kind"], extra: Partial<Card> = {}): Card =>
  ({ id, name: id, kind, aliases: [], match_case: false, exclusions: [], summary: "", facts: [], relations: [], ...extra }) as Card;
const when = (at: number | null, extra: Partial<NonNullable<Card["when"]>> = {}) => ({ chapter: null, at, end: null, label: null, approx: false, outside: false, ...extra });
const typeEra = [{ label: "type", value: "Era", from: null, until: null }];
const rel = (other: Card, label = "involved", extra = {}) => ({ label, other: { id: other.id, name: other.name, kind: other.kind }, standing: "canon", from: null, until: null, ...extra });

describe("eras", () => {
  const lamp = card("the Lamp Years", "event", { facts: typeEra, when: when(280), era_colour: "teal" });
  const ebb = card("the Long Ebb", "event", { facts: typeEra, when: when(290, { end: 300 }) });
  const tide = card("the High Tide", "event", { facts: typeEra, when: when(295, { end: 330 }) });
  const eras = erasOf([lamp, ebb, tide], timeline);

  it("an event typed era (any capitals) with a span; nested ones deeper; one with no end runs on", () => {
    expect(eras.map((e) => e.name)).toEqual(["the Lamp Years", "the Long Ebb", "the High Tide"]);
    expect(eras.find((e) => e.name === "the Lamp Years")!).toMatchObject({ colour: "teal", end: null, depth: 0 });
    expect(eras.find((e) => e.name === "the Long Ebb")!.depth).toBe(1);
  });

  it("a time's era is the innermost; between two overlapping without nesting, the later start", () => {
    expect(eraAt(285, eras)?.name).toBe("the Lamp Years");
    expect(eraAt(292, eras)?.name).toBe("the Long Ebb");
    expect(eraAt(298, eras)?.name).toBe("the High Tide");
    expect(eraAt(5000, eras)?.name).toBe("the Lamp Years");
    expect(eraAt(100, eras)).toBeNull();
    expect(eraAt(null, eras)).toBeNull();
  });
});

describe("ages", () => {
  const seyla = card("Seyla", "character", {
    facts: [
      { label: "born", value: "", from: null, until: null, from_time: -1000 },
      { label: "status", value: "dead", from: "c9", until: null },
    ],
  });
  const byId = new Map([[seyla.id, seyla]]);

  it("from the born fact and the status the Continuity check reads as dead", () => {
    const b = birthOf(seyla, byId, chapters)!;
    const d = deathOf(seyla, byId, chapters)!;
    expect(b).toEqual({ t: -1000, approx: false });
    expect(d.t).toBe(312);
    expect(ageText(b, null, { t: 312, approx: false })).toBe("age 1312");
    expect(ageText(b, d, { t: -800, approx: false })).toBe("age 200");
    expect(ageText(b, d, { t: 400, approx: false })).toBe("died at 1312");
    expect(ageText(b, d, { t: -1200, approx: false })).toBe("not born yet");
    expect(ageText({ t: 278, approx: true }, null, { t: 312.6, approx: false })).toBe("about 34");
  });

  it("from a canon birth event they are involved in", () => {
    const birth = card("Birth of Tamsin", "event", { facts: [{ label: "type", value: "birth", from: null, until: null }], when: when(390) });
    const tamsin = card("Tamsin", "character", { relations: [rel(birth)] });
    const m = new Map([birth, tamsin].map((c) => [c.id, c]));
    expect(birthOf(tamsin, m, chapters)).toEqual({ t: 390, approx: false });
    const rumoured = card("Tamsin", "character", { relations: [rel(birth, "involved", { standing: "rumour" })] });
    expect(birthOf(rumoured, m, chapters)).toBeNull();
  });
});

describe("the Timeline's model", () => {
  const founding = card("The Founding", "event", { when: when(0) });
  const inCh = card("The Wreck", "event", { when: when(null, { chapter: "c3" }) });
  const vision = card("The Opening Vision", "event", { when: when(null, { outside: true }) });
  const lost = card("The Lost Charter", "event");
  const seyla = card("Seyla", "character", { facts: [{ label: "born", value: "", from: null, until: null, from_time: -1000 }], relations: [rel(founding)] });
  founding.relations = [rel(seyla)];
  const cards = [founding, inCh, vision, lost, seyla];
  const chron: Chronology = { presence: [], tellings: [] } as unknown as Chronology;
  const model = buildModel(cards, timeline, [], chron);

  it("marks at their times, the book's band without the tale, outside time apart, the unplaced in the tray", () => {
    expect(model.marks.find((m) => m.label === "The Founding")!.t).toBe(0);
    expect(model.marks.find((m) => m.label === "The Wreck")!.t).toBe(312);
    expect(model.marks.find((m) => m.kind === "birth")!.label).toBe("Seyla born");
    expect(model.marks.find((m) => m.id === "ch:c14")!.label).toBe("14 · The Drowned Bell — tale");
    expect(model.book).toEqual({ start: 312, end: 312 });
    expect(model.outside.map((o) => o.label)).toEqual(["The Opening Vision"]);
    expect(model.unplaced.map((o) => o.name)).toEqual(["The Lost Charter"]);
  });

  it("lanes: events, the book, a character's life line and their age at each event", () => {
    const lanes = buildLanes(model, ["Seyla"], { kinds: new Set(["event", "chapter", "birth", "death", "move"]), entries: new Set(), standings: new Set(["canon"]) }, new Map(cards.map((c) => [c.id, c])), timeline, null, chron);
    expect(lanes.map((l) => l.key)).toEqual(["events", "book", "Seyla"]);
    // births stay out of the main lane unless it is filtered to entries
    expect(lanes[0]!.marks.some((m) => m.kind === "birth")).toBe(false);
    const s = lanes[2]!;
    expect(s.segments.find((x) => x.tone === "life")).toMatchObject({ t: -1000, fade: "end" });
    expect(s.marks.find((m) => m.kind === "event")!.label).toBe("The Founding (1000)");
    expect(s.counts).toBe("Seyla · 1 event · 0 places");
  });

  it("in this span: what overlaps it", () => {
    expect(inSpan(model.marks, 290, 312).map((m) => m.label)).toContain("The Wreck");
    expect(inSpan(model.marks, 290, 312).map((m) => m.label)).not.toContain("The Founding");
  });
});

describe("the axis", () => {
  const times = [-1000, -800, 0, 312];

  it("is to scale, except that long empty stretches fold to a fixed width", () => {
    const a = makeAxis(times, 1, 0, 220);
    expect(a.folds.map((f) => f.length)).toEqual([800, 312]);
    expect(a.x(-800) - a.x(-1000)).toBe(200);
    expect(a.x(0) - a.x(-800)).toBe(FOLD_W);
    // and back again
    expect(a.t(a.x(-900))).toBeCloseTo(-900);
    expect(a.t(a.x(100))).toBeCloseTo(100);
  });

  it("folds are worked out again as the scale changes", () => {
    expect(makeAxis(times, 0.2, 0, 220).folds).toHaveLength(0);
    expect(makeAxis(times, 0.5, 0, 220).folds.map((f) => f.length)).toEqual([800]);
  });

  it("fit fills as much of the width as it can", () => {
    const k = fitScale([380, 390, 410, 412, 413, 414], 1000, 40, 250);
    expect(makeAxis([380, 390, 410, 412, 413, 414], k, 40, 250).width).toBeGreaterThan(800);
    const k2 = fitScale(times, 1000, 40, 250);
    expect(makeAxis(times, k2, 40, 250).width).toBeLessThanOrEqual(1000);
  });

  it("ticks are round and never inside a fold", () => {
    const a = makeAxis(times, 1, 0, 220);
    const ts = ticks(a, 0, a.width);
    expect(ts.every((t) => !(t > -800 && t < 0) && !(t > 0 && t < 312))).toBe(true);
    expect(ts).toContain(-900);
  });

  it("zoom steps are a factor of √2", () => {
    expect(stepOf(1)).toBe(0);
    expect(stepOf(2)).toBe(2);
    expect(scaleOfStep(stepOf(5.2))).toBeCloseTo(5.66, 1);
  });
});

describe("clusters", () => {
  const marks = Array.from({ length: 20 }, (_, i) => ({ id: `m${i}`, kind: i < 14 ? "event" : i < 17 ? "birth" : "move", t: 300 + i * 0.1, t2: null, approx: false, label: `m${i}`, about: [] })) as Parameters<typeof cluster>[0];

  it("far out, marks that would overlap merge with a count and a breakdown; close in they split", () => {
    const far = cluster(marks, makeAxis(marks.map((m) => m.t), 1));
    expect(far).toHaveLength(1);
    expect(far[0]!.cluster!.marks).toHaveLength(20);
    expect(far[0]!.cluster!.breakdown).toBe("14 events · 3 births · 3 moves");
    const near = cluster(marks, makeAxis(marks.map((m) => m.t), 200));
    expect(near.every((x) => x.mark)).toBe(true);
    expect(breakdown(marks.slice(0, 1))).toBe("1 event");
  });

  it("a dense stretch is several clusters, none wider than the gap", () => {
    const dense = Array.from({ length: 200 }, (_, i) => ({ ...marks[0]!, id: `d${i}`, t: i })) as typeof marks;
    const items = cluster(dense, makeAxis(dense.map((m) => m.t), 1, 0, 1e9));
    expect(items.length).toBe(15);
    expect(items.every((x) => x.cluster && x.cluster.marks.length <= 14)).toBe(true);
  });
});

describe("an entry's own timeline", () => {
  it("a character: born, their events, a relationship from a chapter, died, with ages, in happened order", () => {
    const founding = card("The Founding", "event", { when: when(0) });
    const varren = card("Varren", "character");
    const seyla = card("Seyla", "character", {
      facts: [
        { label: "born", value: "", from: null, until: null, from_time: -1000 },
        { label: "status", value: "dead", from: "c9", until: null },
      ],
      relations: [rel(founding, "took part in"), rel(varren, "married to", { from: "c3" })],
    });
    const byId = new Map([founding, varren, seyla].map((c) => [c.id, c]));
    const rows = entitySlice({ card: seyla, cards: byId, timeline, chronology: null, eras: [], unit: u });
    expect(rows.map((r) => r.text)).toEqual(["born", "took part in The Founding", "married to Varren", "died"]);
    expect(rows.map((r) => r.age)).toEqual([undefined, "age 1000", "age 1312", "at 1312"]);
    expect(rows[0]!.when).toBe("year −1000");
  });
});

describe("names on a lane", () => {
  // 6 px a letter; shortening keeps the first letters that fit and adds "…"
  const measure = (t: string) => t.length * 6;
  const fit = (t: string, room: number) => {
    const n = Math.floor(room / 6) - 1;
    return n >= 3 ? `${t.slice(0, n)}…` : "";
  };
  const opts = { rows: 2, width: 400, measure, fit };
  const at = (...xs: [number, string][]) => xs.map(([x, text]) => ({ x, text, pad: 7 }));

  it("beside the mark when there is room, a row up when it would run over the next mark", () => {
    const spots = placeLabels(at([10, "The Spring Flood"], [60, "The Raising"], [300, "Ash"]), opts);
    // the first name would run to x 113, over the second mark: a row up; the second beside its own mark
    expect(spots[0]).toEqual({ row: 1, left: false, text: "The Spring Flood" });
    expect(spots[1]).toEqual({ row: 0, left: false, text: "The Raising" });
    expect(spots[2]).toEqual({ row: 0, left: false, text: "Ash" });
  });

  it("near the right edge, to the left of the mark instead of off the edge", () => {
    const spots = placeLabels(at([380, "The Mountain Fires"]), opts);
    expect(spots[0]).toEqual({ row: 0, left: true, text: "The Mountain Fires" });
  });

  it("shortened where nothing whole fits, and never on another name", () => {
    const spots = placeLabels(at([10, "A".repeat(40)], [20, "B".repeat(40)], [30, "C".repeat(60)]), { ...opts, width: 300 });
    const boxes = spots.map((s, i) => (s ? { row: s.row, x0: s.left ? 10 * (i + 1) - 7 - measure(s.text) : 10 * (i + 1) + 7, w: measure(s.text) } : null));
    for (const a of boxes) for (const b of boxes) if (a && b && a !== b && a.row === b.row) expect(a.x0 + a.w <= b.x0 || b.x0 + b.w <= a.x0).toBe(true);
    for (const b of boxes) if (b) expect(b.x0 + b.w).toBeLessThanOrEqual(300);
    expect(spots.some((s) => s?.text.endsWith("…")) || spots.some((s) => s === null)).toBe(true);
  });
});
