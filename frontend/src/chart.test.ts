import { describe, expect, it } from "vitest";

import { changesBetween, chartState, holdsCount, inside, layoutChart, pinKey, placeChartLabels, shapeOf, shapePath, shapeSpan, type Pin, type StateInput } from "./world/chart";
import type { GraphData } from "./world/graph";
import type { IndexOf } from "./world/time";

// Phase 12d (docs/SPEC.md §13.7): the chart's state as of a point, shapes from types, the layout from the inside out
// with pins, and what changed between two states. The places: the Iron Vale holding Old Harbour and Greywick, Old
// Harbour holding the Quay and the Lamp House, the Grey Sea holding the Isle of Wrens, the Salt Marches beside the Vale.
const P = ["the Iron Vale", "Old Harbour", "Greywick", "the Quay", "the Lamp House", "the Grey Sea", "the Isle of Wrens", "the Salt Marches", "the Old Mill"];
const TYPES: Record<string, string> = { "the Iron Vale": "Land", "Old Harbour": "city", Greywick: "town", "the Quay": "district", "the Lamp House": "building", "the Grey Sea": "sea", "the Isle of Wrens": "island", "the Salt Marches": "duchy" };
let n = 0;
const edge = (a: string, label: string, b: string, extra: Partial<GraphData["edges"][number]> = {}) => ({
  id: `e${n++}`, a, b, type_id: label, label, reverse_label: label === "inside" ? "contains" : label === "north of" ? "south of" : label === "controls" ? "controlled by" : null,
  standing: "canon" as const, from_chapter_id: null, until_chapter_id: null, ...extra,
});
const data = (edges: GraphData["edges"], presence: GraphData["presence"] = []): GraphData => ({
  nodes: [...P.map((id) => ({ id, name: id, kind: "place" as const, summary: "" })), { id: "Varren", name: "Varren", kind: "character", summary: "" }, { id: "the Lamp Guild", name: "the Lamp Guild", kind: "faction", summary: "" }, { id: "the River Wardens", name: "the River Wardens", kind: "faction", summary: "" }],
  edges, types: [], presence, cooccurrence: [],
});
const base = () => [
  edge("Old Harbour", "inside", "the Iron Vale"), edge("Greywick", "inside", "the Iron Vale"), edge("the Quay", "inside", "Old Harbour"),
  edge("the Lamp House", "inside", "Old Harbour"), edge("the Isle of Wrens", "inside", "the Grey Sea"), edge("the Old Mill", "inside", "the Iron Vale"),
  edge("the Iron Vale", "borders", "the Salt Marches"), edge("Old Harbour", "road to", "Greywick"), edge("Old Harbour", "sea route to", "the Isle of Wrens"),
  edge("Greywick", "north of", "Old Harbour"),
];
const indexOf = Object.assign((id: string | null) => (id ? Number(id.slice(1)) : undefined), { timeOf: () => 312 }) as IndexOf;
const input = (g: GraphData, extra: Partial<StateInput> = {}): StateInput => ({
  data: g, cards: new Map(), typeOf: (id) => (TYPES[id] ? [TYPES[id]!] : []), shapes: { duchy: "hexagon" }, mentions: new Map([["Old Harbour", 30], ["Greywick", 5]]),
  asOf: null, indexOf, chapter: null, standings: new Set(["canon", "planned"]), ...extra,
});

describe("shapes from types", () => {
  it("the list with its synonyms, any capitals, the world's own, the first that maps", () => {
    expect(shapeOf(["Kingdom"], {}).shape).toBe("hexagon");
    expect(shapeOf(["hamlet"], {}).shape).toBe("circle");
    expect(shapeOf(["duchy"], {}).shape).toBe("none");
    expect(shapeOf(["duchy"], { duchy: "hexagon" }).shape).toBe("hexagon");
    expect(shapeOf(["holy site", "Bay"], {})).toEqual({ type: "Bay", shape: "water" });
    expect(shapeOf([], {})).toEqual({ type: null, shape: "none" });
    for (const s of ["hexagon", "circle", "rounded", "square", "water", "ribbon", "triangle", "scalloped", "none"] as const) expect(shapePath(s, 20, false)).toMatch(/^M.*Z$/);
  });
});

describe("the state as of a point", () => {
  const s = chartState(input(data(base())));

  it("nesting, borders, routes and directions", () => {
    expect(s.roots).toEqual(["the Grey Sea", "the Iron Vale", "the Salt Marches"]);
    expect(s.places.get("the Iron Vale")!.children).toEqual(["Greywick", "Old Harbour", "the Old Mill"]);
    expect(s.places.get("the Salt Marches")!.shape).toBe("hexagon");
    expect(s.places.get("the Old Mill")).toMatchObject({ shape: "none", level: 2 });
    expect(s.places.get("the Lamp House")!.level).toBe(3);
    expect(s.borders).toEqual([{ a: "the Iron Vale", b: "the Salt Marches", standing: "canon" }]);
    expect(s.routes.map((r) => r.kind)).toEqual(["road", "sea"]);
    expect(s.north).toEqual([["Greywick", "Old Harbour"]]);
    // named often: a little larger
    expect(s.places.get("Old Harbour")!.step).toBe(3);
    expect(s.places.get("Greywick")!.step).toBe(1);
    expect(holdsCount(s, "Old Harbour")).toBe(2);
    expect(inside(s, "the Iron Vale")).toEqual(["Greywick", "Old Harbour", "the Lamp House", "the Quay", "the Old Mill"]);
  });

  it("a place inside two is drawn in the first recorded; a loop stays at the top, as in the place tree", () => {
    const t = chartState(input(data([...base(), edge("the Quay", "inside", "Greywick")])));
    expect(t.places.get("the Quay")).toMatchObject({ parent: "Old Harbour", alsoIn: ["Greywick"] });
    const loop = chartState(input(data([...base(), edge("the Iron Vale", "inside", "the Quay")])));
    expect(["the Quay", "Old Harbour", "the Iron Vale"].map((id) => loop.places.get(id)!.parent)).toEqual([null, null, null]);
  });

  it("who controls, who is there, as of a chapter", () => {
    const g = data([...base(), edge("the Lamp Guild", "controls", "Greywick", { until_chapter_id: "c4" }), edge("the River Wardens", "controls", "Greywick", { from_chapter_id: "c5" }), edge("the River Wardens", "controls", "Old Harbour")], [{ entity_id: "Varren", place_id: "Old Harbour", chapter_id: "c4" }]);
    const at4 = chartState(input(g, { asOf: 4, chapter: "c4" }));
    expect(at4.control.get("Greywick")).toEqual(["the Lamp Guild"]);
    expect(at4.here.get("Old Harbour")).toEqual(["Varren"]);
    const at6 = chartState(input(g, { asOf: 6, chapter: "c6" }));
    expect(at6.control.get("Greywick")).toEqual(["the River Wardens"]);
    expect(at6.factions).toEqual(["the River Wardens"]);
    expect(at6.here.size).toBe(0);
    // what changed between them
    const ch = changesBetween(at4, at6, (id) => id);
    expect(ch).toEqual([{ place: "Greywick", parts: ["controlled by the Lamp Guild → the River Wardens"] }]);
    const b = data([...base().filter((e) => e.label !== "borders"), edge("the Iron Vale", "borders", "the Salt Marches", { until_chapter_id: "c12" })]);
    expect(changesBetween(chartState(input(b, { asOf: 12 })), chartState(input(b, { asOf: 13 })), (id) => id)).toEqual([{ place: "the Salt Marches", parts: ["no longer borders the Iron Vale"] }]);
  });
});

describe("the layout", () => {
  const s = chartState(input(data(base())));
  const pins = new Map<string, Pin>();
  const lay = layoutChart(s, pins);
  const at = (id: string) => lay.laid.get(id)!;
  const insideOf = (i: string, o: string) => Math.hypot(at(i).ax - at(o).ax, at(i).ay - at(o).ay) + at(i).r <= at(o).r + 0.5;

  it("contents inside their container, a container as large as what it holds, the same each time", () => {
    for (const [i, o] of [["Old Harbour", "the Iron Vale"], ["the Quay", "Old Harbour"], ["the Lamp House", "Old Harbour"], ["the Isle of Wrens", "the Grey Sea"]]) expect(insideOf(i!, o!)).toBe(true);
    expect(at("the Iron Vale").r).toBeGreaterThan(at("Old Harbour").r);
    const again = layoutChart(s, pins);
    expect(again.laid.get("Greywick")!.ax).toBeCloseTo(at("Greywick").ax);
  });

  it("borders touch, north is up", () => {
    const v = at("the Iron Vale");
    const m = at("the Salt Marches");
    expect(Math.abs(Math.hypot(v.ax - m.ax, v.ay - m.ay) - (v.r + m.r))).toBeLessThan(12);
    expect(at("Greywick").ay).toBeLessThan(at("Old Harbour").ay);
    expect(lay.unplaced).toEqual([]);
  });

  it("a pin is kept relative to its container; one it can't honour is listed", () => {
    const pinned = new Map([[pinKey("Greywick", "the Iron Vale"), { place_id: "Greywick", container_id: "the Iron Vale", x: 40, y: -30 }]]);
    const l = layoutChart(s, pinned);
    expect(l.laid.get("Greywick")).toMatchObject({ x: 40, y: -30, pinned: true });
    // a pin for another container doesn't apply here
    const other = new Map([[pinKey("Greywick", "the Grey Sea"), { place_id: "Greywick", container_id: "the Grey Sea", x: 400, y: 400 }]]);
    expect(layoutChart(s, other).laid.get("Greywick")!.pinned).toBe(false);
    const both = chartState(input(data([...base(), edge("Old Harbour", "north of", "Greywick")])));
    expect(layoutChart(both, new Map()).unplaced.join()).toContain("each recorded on the other's side");
  });

  it("filters leave places out", () => {
    const l = layoutChart(s, pins, (id) => s.places.get(id)!.level <= 2);
    expect(l.laid.has("the Quay")).toBe(false);
    expect(l.laid.has("Old Harbour")).toBe(true);
  });
});

describe("names on the chart", () => {
  it("a shape's reach: a hexagon's points and sides, a circle's chord", () => {
    const h = shapeSpan("hexagon", 100, true);
    expect(h.top).toBeCloseTo(-115.47, 1);
    expect(h.half(0)).toBe(100);
    expect(h.half(-110)).toBeLessThan(10);
    expect(shapeSpan("circle", 50, false).half(30)).toBeCloseTo(40, 5);
  });

  it("an open container's name inside along the top, lower where its point is too narrow", () => {
    const [d] = placeChartLabels([{ id: "d", x: 0, y: 0, shape: "hexagon", r: 200, open: true, w: 120, h: 12 }], { circles: [], segments: [] });
    // inside the outline, below the point
    expect(d!.y).toBeGreaterThan(-231);
    expect(d!.y).toBeLessThan(-100);
    expect(shapeSpan("hexagon", 200, true).half(d!.y - 12)).toBeGreaterThanOrEqual(60);
  });

  it("a name moves off a road and a dot to a clear side, inside its container", () => {
    const places = [
      { id: "land", x: 0, y: 0, shape: "circle" as const, r: 200, open: true, w: 60, h: 12 },
      { id: "town", x: 0, y: 0, shape: "circle" as const, r: 20, open: false, w: 50, h: 12, parent: "land" },
    ];
    // a road straight down from the town, and someone's dot just above it
    const out = placeChartLabels(places, { circles: [{ x: 0, y: -26, r: 4 }], segments: [{ x1: 0, y1: 20, x2: 0, y2: 120 }] });
    const town = out.find((l) => l.id === "town")!;
    expect(town.anchor).not.toBe("middle");
  });

  it("shortened when nowhere holds the whole name", () => {
    const places = [
      { id: "room", x: 0, y: 0, shape: "square" as const, r: 30, open: true, w: 40, h: 10 },
      { id: "nook", x: 0, y: 0, shape: "square" as const, r: 8, open: false, w: 300, h: 10, parent: "room", shorten: (max: number) => (max > 20 ? { text: "The Cou…", w: Math.min(max, 30) } : null) },
    ];
    const nook = placeChartLabels(places, { circles: [], segments: [] }).find((l) => l.id === "nook")!;
    expect(nook.text).toBe("The Cou…");
  });
});
