import { describe, expect, it } from "vitest";

import { clusters, neighbourhood, placeTree, visibleLinks, type GraphData, type Link } from "./world/graph";

const link = (a: string, b: string): Link => ({ a, b, kind: "recorded", label: "knows", weight: 1 });

describe("clusters", () => {
  it("separates two groups that only know each other through one character", () => {
    const left = ["a1", "a2", "a3", "a4"];
    const right = ["b1", "b2", "b3", "b4"];
    const links: Link[] = [];
    for (const g of [left, right]) for (let i = 0; i < g.length; i++) for (let j = i + 1; j < g.length; j++) links.push(link(g[i]!, g[j]!));
    links.push(link("bridge", "a1"), link("bridge", "b1"));
    const c = clusters([...left, ...right, "bridge", "loner"], links);
    expect(new Set(left.map((x) => c.get(x))).size).toBe(1);
    expect(new Set(right.map((x) => c.get(x))).size).toBe(1);
    expect(c.get("a1")).not.toBe(c.get("b1"));
    expect([c.get("a1"), c.get("b1")]).toContain(c.get("bridge"));
    expect(c.get("loner")).toBe(-1);
  });

  it("is the same every time", () => {
    const links = [link("x", "y"), link("y", "z"), link("z", "x"), link("p", "q")];
    expect([...clusters(["x", "y", "z", "p", "q"], links)]).toEqual([...clusters(["q", "p", "z", "y", "x"], links)]);
  });
});

describe("neighbourhood", () => {
  it("finds who someone knows directly and through one other person", () => {
    const links = [link("varren", "isolde"), link("isolde", "mordoch"), link("mordoch", "far")];
    const n = neighbourhood(links, "varren", 2);
    expect([...n]).toEqual([["varren", 0], ["isolde", 1], ["mordoch", 2]]);
  });
});

const data: GraphData = {
  nodes: [
    { id: "v", name: "Varren", kind: "character", summary: "" },
    { id: "i", name: "Isolde", kind: "character", summary: "" },
    { id: "h", name: "Old Harbour", kind: "place", summary: "" },
    { id: "l", name: "Lamphouse", kind: "place", summary: "" },
  ],
  edges: [
    { id: "1", a: "v", b: "i", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "canon", from_chapter_id: "c2", until_chapter_id: null },
    { id: "2", a: "l", b: "h", type_id: "inside", label: "inside", reverse_label: "contains", standing: "canon", from_chapter_id: null, until_chapter_id: null },
    { id: "3", a: "i", b: "l", type_id: "lives", label: "lives in", reverse_label: "home of", standing: "canon", from_chapter_id: null, until_chapter_id: null },
    { id: "4", a: "v", b: "h", type_id: "rules", label: "rules", reverse_label: "ruled by", standing: "rumour", from_chapter_id: null, until_chapter_id: null },
  ],
  types: [],
  presence: [{ entity_id: "v", place_id: "h", chapter_id: "c2" }],
  cooccurrence: [{ a: "h", b: "i", by_chapter: { c1: 1, c2: 2 } }],
};
const order = ["c1", "c2"];
const indexOf = (id: string | null) => (id && order.includes(id) ? order.indexOf(id) : undefined);
const all = { kinds: new Set(["character", "place"]), standings: new Set(["canon", "planned", "rumour"]), typeIds: new Set<string>(), indexOf };

describe("visibleLinks", () => {
  it("shows what holds as of a chapter, and co-occurrence up to it", () => {
    const at0 = visibleLinks(data, { ...all, asOf: 0, coMin: 1 });
    expect(at0.map((l) => l.label)).toEqual(["inside", "lives in", "rules", "named together in 1 paragraph"]);
    const at1 = visibleLinks(data, { ...all, asOf: 1, coMin: 3 });
    expect(at1.map((l) => l.label)).toEqual(["parent of", "inside", "lives in", "rules", "named together in 3 paragraphs"]);
    const canon = visibleLinks(data, { ...all, standings: new Set(["canon"]), asOf: null, coMin: 0 });
    expect(canon.map((l) => l.label)).toEqual(["parent of", "inside", "lives in"]);
  });
});

describe("placeTree", () => {
  it("nests places and lists who lives there and who is there in a chapter", () => {
    const t = placeTree(data, 1, indexOf, "c2");
    expect(t.map((p) => p.name)).toEqual(["Old Harbour"]);
    expect(t[0]!.here.map((x) => x.name)).toEqual(["Varren"]);
    // a rumour doesn't put anyone anywhere
    expect(t[0]!.people).toEqual([]);
    const lamp = t[0]!.children[0]!;
    expect(lamp.name).toBe("Lamphouse");
    expect(lamp.people).toEqual([{ label: "home of", who: [{ id: "i", name: "Isolde", kind: "character", summary: "" }] }]);
  });
});
