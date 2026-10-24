import { describe, expect, it } from "vitest";

import type { Gender } from "./types";
import { Family, familyLinks, kinOf, kinText, kinWord, layoutTree, readType, type Kin } from "./world/family";
import type { GraphData } from "./world/graph";

// Phase 11 §12.2: the family tree. Varren is the father of Isolde and Oswin, Oswin the father of Mirelle, and Varren
// marries Seyla in chapter 3.
const order = ["c1", "c2", "c3", "c4"];
const indexOf = (id: string | null) => (id && order.includes(id) ? order.indexOf(id) : undefined);

function world(genders: Record<string, Gender | null> = {}, extra: GraphData["edges"] = []): GraphData {
  const names = ["Varren", "Isolde", "Oswin", "Mirelle", "Seyla", "Bren", "Ash", "Logbook"];
  const g: Record<string, Gender | null> = { Varren: "male", Isolde: "female", Oswin: "male", Mirelle: "female", Seyla: "female", ...genders };
  const types = [
    { id: "parent", a_kind: "character", b_kind: "character", label: "parent of", reverse_label: "child of" },
    { id: "married", a_kind: "character", b_kind: "character", label: "married to", reverse_label: null },
    { id: "sibling", a_kind: "character", b_kind: "character", label: "sibling of", reverse_label: null },
    { id: "friend", a_kind: "character", b_kind: "character", label: "friend of", reverse_label: null },
  ];
  const e = (id: string, a: string, b: string, type: string, from: string | null = null, standing: "canon" | "planned" | "rumour" = "canon") => {
    const t = types.find((x) => x.id === type)!;
    return { id, a, b, type_id: type, label: t.label, reverse_label: t.reverse_label, standing, from_chapter_id: from, until_chapter_id: null };
  };
  return {
    nodes: names.map((n) => ({ id: n, name: n, kind: n === "Logbook" ? "object" : "character", summary: "", gender: g[n] ?? null, project: null })),
    edges: [
      e("1", "Varren", "Isolde", "parent"),
      e("2", "Varren", "Oswin", "parent"),
      e("3", "Oswin", "Mirelle", "parent"),
      e("4", "Varren", "Seyla", "married", "c3"),
      e("5", "Isolde", "Bren", "friend"),
      ...extra,
    ],
    types,
    presence: [],
    cooccurrence: [],
  };
}

const ALL = new Set(["canon", "planned", "rumour"]);
const fam = (d: GraphData, asOf: number | null = null) => new Family(familyLinks(d, { asOf, indexOf, standings: ALL }));
const gender = (d: GraphData) => (id: string) => d.nodes.find((n) => n.id === id)?.gender ?? null;
const listed = (d: GraphData, centre: string, asOf: number | null = null) =>
  kinOf(fam(d, asOf), centre)
    .filter((k) => !k.recorded)
    .map((k: Kin) => `${kinText(k, gender(d)(k.id))}: ${k.id}${k.via.length ? ` (via ${k.via.join(" → ")})` : ""}`)
    .sort();

describe("the family tree", () => {
  it("reads types by their label, like the place tree reads inside", () => {
    expect(readType("parent of", "child of")).toEqual({ kind: "parent", dir: 1 });
    expect(readType("adoptive parent of", null)).toEqual({ kind: "parent", dir: 1 });
    expect(readType("guardian", "daughter of")).toEqual({ kind: "parent", dir: 1 });
    expect(readType("son of", "father of")).toEqual({ kind: "parent", dir: -1 });
    expect(readType("grandparent of", null)).toBeNull();
    expect(readType("Wed to", null)).toEqual({ kind: "married", dir: 1 });
    expect(readType("sibling of", null)).toEqual({ kind: "sibling", dir: 1 });
    expect(readType("friend of", null)).toBeNull();
  });

  it("done when: Isolde's page lists brother Oswin, niece Mirelle and stepmother Seyla, with their paths", () => {
    const d = world();
    expect(listed(d, "Isolde")).toEqual(["brother: Oswin (via Varren)", "niece: Mirelle (via Varren → Oswin)", "stepmother: Seyla (via Varren)"]);
    // none of it is recorded, and nothing outside the family counts (Bren is a friend)
    expect(kinOf(fam(d), "Isolde").filter((k) => k.recorded).map((k) => k.id)).toEqual(["Varren"]);
  });

  it("done when: from Mirelle, Varren is grandfather and Isolde aunt; not set or nonbinary give the general words", () => {
    const d = world();
    expect(listed(d, "Mirelle")).toEqual(["aunt: Isolde (via Oswin → Varren)", "grandfather: Varren (via Oswin)"]);
    const unset = world({ Isolde: null, Oswin: "nonbinary" });
    expect(listed(unset, "Mirelle")).toContain("parent's sibling: Isolde (via Oswin → Varren)");
    expect(listed(unset, "Isolde")).toContain("sibling: Oswin (via Varren)");
  });

  it("done when: as of chapter 2 Seyla is in neither the tree nor Isolde's list", () => {
    const d = world();
    expect(listed(d, "Isolde", 1)).toEqual(["brother: Oswin (via Varren)", "niece: Mirelle (via Varren → Oswin)"]);
    const tree = layoutTree(fam(d, 1), "Mirelle");
    expect(tree.people.map((p) => p.id).sort()).toEqual(["Isolde", "Mirelle", "Oswin", "Varren"]);
  });

  it("done when: the tree centred on Mirelle has three generations with Varren and Seyla as a couple", () => {
    const tree = layoutTree(fam(world()), "Mirelle");
    const at = new Map(tree.people.map((p) => [p.id, p]));
    expect(new Set(tree.people.map((p) => p.gen)).size).toBe(3);
    expect(at.get("Varren")!.gen).toBe(0);
    expect(at.get("Seyla")!.gen).toBe(0);
    expect([at.get("Isolde")!.gen, at.get("Oswin")!.gen, at.get("Mirelle")!.gen]).toEqual([1, 1, 2]);
    // side by side, joined by a married line
    expect(Math.abs(at.get("Varren")!.x - at.get("Seyla")!.x)).toBe(150);
    expect(tree.lines.filter((l) => l.kind === "married")).toHaveLength(1);
    // children hang under their parents
    expect(tree.lines.filter((l) => l.kind === "child")).toHaveLength(3);
    expect(at.get("Mirelle")!.x).toBe(at.get("Oswin")!.x);
  });

  it("works out cousins, half-siblings, in-laws, great-grandparents and relatives", () => {
    const extra = [
      // Isolde has Ash with Bren: Ash and Mirelle are cousins
      { id: "6", a: "Isolde", b: "Ash", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "canon" as const, from_chapter_id: null, until_chapter_id: null },
      { id: "7", a: "Bren", b: "Ash", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "rumour" as const, from_chapter_id: null, until_chapter_id: null },
      // Seyla is also Oswin's mother; Isolde's mother isn't recorded, so Isolde and Oswin are half-siblings? only if
      // each has a parent the other doesn't
      { id: "8", a: "Seyla", b: "Oswin", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "canon" as const, from_chapter_id: null, until_chapter_id: null },
    ];
    const d = world({ Ash: null, Bren: "male" }, extra);
    const ash = listed(d, "Ash");
    expect(ash).toContain("cousin: Mirelle (via Isolde → Varren → Oswin)");
    expect(ash).toContain("grandfather: Varren (via Isolde)");
    expect(ash).toContain("uncle: Oswin (via Isolde → Varren)");
    // Isolde has no parent Oswin lacks, so they are plain siblings; Oswin has Seyla, but "each" is needed
    expect(listed(d, "Isolde")).toContain("brother: Oswin (via Varren)");
    // a spouse's parent and sibling, a child's spouse
    const married = world({ Bren: "male" }, [{ id: "9", a: "Oswin", b: "Bren", type_id: "married", label: "married to", reverse_label: null, standing: "canon" as const, from_chapter_id: null, until_chapter_id: null }]);
    expect(listed(married, "Bren")).toEqual(expect.arrayContaining(["father-in-law: Varren (via Oswin)", "sister-in-law: Isolde (via Oswin → Varren)", "stepdaughter: Mirelle (via Oswin)"]));
    expect(listed(married, "Varren")).toContain("son-in-law: Bren (via Oswin)");
    expect(kinWord("grandparent", "female", 2)).toBe("great-great-grandmother");
    expect(kinWord("parent's sibling", null)).toBe("parent's sibling");
  });

  it("two people related in two ways show both, and a recorded sibling isn't worked out again", () => {
    const d = world({}, [
      { id: "10", a: "Isolde", b: "Oswin", type_id: "sibling", label: "sibling of", reverse_label: null, standing: "canon", from_chapter_id: null, until_chapter_id: null },
    ]);
    const k = kinOf(fam(d), "Isolde").filter((x) => x.id === "Oswin");
    expect(k.map((x) => [x.relation, x.recorded])).toEqual([["sibling", true]]);
    // cousins who marry
    const cousins = world({}, [
      { id: "11", a: "Seyla", b: "Bren", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "canon", from_chapter_id: null, until_chapter_id: null },
      { id: "12", a: "Isolde", b: "Ash", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "canon", from_chapter_id: null, until_chapter_id: null },
      { id: "13", a: "Ash", b: "Mirelle", type_id: "married", label: "married to", reverse_label: null, standing: "canon", from_chapter_id: null, until_chapter_id: null },
    ]);
    expect(kinOf(fam(cousins), "Ash").filter((x) => x.id === "Mirelle").map((x) => x.relation).sort()).toEqual(["cousin", "spouse"]);
  });

  it("planned and rumoured links count unless hidden, and other types are left out", () => {
    const d = world({}, [{ id: "14", a: "Bren", b: "Mirelle", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "rumour", from_chapter_id: null, until_chapter_id: null }]);
    expect(fam(d).get(fam(d).parents, "Mirelle")).toEqual(new Set(["Oswin", "Bren"]));
    const canonOnly = new Family(familyLinks(d, { asOf: null, indexOf, standings: new Set(["canon"]) }));
    expect(canonOnly.get(canonOnly.parents, "Mirelle")).toEqual(new Set(["Oswin"]));
    const tree = layoutTree(fam(d), "Mirelle");
    expect(tree.lines.filter((l) => l.kind === "child" && l.dashed)).toHaveLength(1);
    expect(tree.lines.filter((l) => l.kind === "coparents")).toHaveLength(1);
  });

  it("someone recorded as their own ancestor is drawn once, with the loop named", () => {
    const d = world({}, [{ id: "15", a: "Mirelle", b: "Varren", type_id: "parent", label: "parent of", reverse_label: "child of", standing: "canon", from_chapter_id: null, until_chapter_id: null }]);
    const f = fam(d);
    expect(f.loops()).toHaveLength(1);
    expect(f.loops()[0]![0]).toBe(f.loops()[0]![3]);
    const tree = layoutTree(f, "Varren");
    expect(tree.people.filter((p) => p.id === "Varren")).toHaveLength(1);
  });

  it("an adoptive parent shows its label on the line; recorded siblings without parents hang from a ?", () => {
    const d = world({}, [
      { id: "16", a: "Seyla", b: "Bren", type_id: "x", label: "adoptive parent of", reverse_label: "adopted child of", standing: "canon", from_chapter_id: null, until_chapter_id: null },
      { id: "17", a: "Ash", b: "Logbook", type_id: "sibling", label: "sibling of", reverse_label: null, standing: "canon", from_chapter_id: null, until_chapter_id: null },
    ]);
    const tree = layoutTree(fam(d), "Bren");
    expect(tree.lines.find((l) => l.label)?.label).toBe("adoptive parent of");
    const k = kinOf(fam(d), "Bren").find((x) => x.id === "Seyla")!;
    expect(kinText(k, "female")).toBe("adoptive parent of");
    // a plain recorded parent gets the word, by gender
    const varren = kinOf(fam(world()), "Isolde").find((x) => x.id === "Varren")!;
    expect([varren.recorded, kinText(varren, "male")]).toEqual([true, "father"]);
    const orphans = world({}, [
      { id: "18", a: "Ash", b: "Bren", type_id: "sibling", label: "sibling of", reverse_label: null, standing: "canon", from_chapter_id: null, until_chapter_id: null },
    ]);
    expect(layoutTree(fam(orphans), "Ash").unknown).toHaveLength(1);
  });
});
