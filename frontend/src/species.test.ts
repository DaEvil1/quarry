import { describe, expect, it } from "vitest";

import { rolesFor } from "./bible";
import { cardDom } from "./editor/strips";
import type { Card } from "./world/cards";
import { Family, familyLinks, kinOf, kinText, layoutTree } from "./world/family";
import type { GraphData } from "./world/graph";
import { groupBy, matches, valuesAtEnd, type LabelReader } from "./world/labels";
import { possessors, SPECIES_COLUMN, speciesAtEnd, speciesColours, speciesText } from "./world/species";
import { holds } from "./world/time";

// Phase 12c (docs/SPEC.md §13.3–§13.5): what a character is beside the name, the characters table's Species column,
// the graph's colouring by species, roles offered per group, and "ancestor of" in the family tree.
const order = ["c1", "c2", "c3", "c4", "c5", "c9", "c10", "c13"];
const indexOf = (id: string | null) => (id && order.includes(id) ? order.indexOf(id) : undefined);
type Rel = Card["relations"][number];
const ref = (name: string, kind: Card["kind"] = "species") => ({ id: name, name, kind });
const rel = (label: string, other: ReturnType<typeof ref>, from: string | null = null, until: string | null = null, standing = "canon"): Rel => ({ label, other, standing, from, until });
const card = (name: string, relations: Rel[], kind: Card["kind"] = "character"): Card => ({
  id: name, name, kind, aliases: [], first_name: null, match_case: true, exclusions: [], summary: "", facts: [], relations,
});
/** A card as it reads at a chapter, the way the cards store does. */
const asOf = (c: Card, chapter: string): Card => {
  const at = indexOf(chapter)!;
  return { ...c, relations: c.relations.filter((r) => holds({ from_chapter_id: r.from, until_chapter_id: r.until }, at, indexOf)) };
};

const seyla = card("Seyla", [rel("is a", ref("selkie")), rel("appears as", ref("human"), "c3", "c9"), rel("married to", ref("Varren", "character"))]);

describe("species beside the name", () => {
  it("shows the species, and the outward form while it holds", () => {
    expect(speciesText(asOf(seyla, "c5"))).toBe("selkie · appears as human");
    expect(speciesText(asOf(seyla, "c10"))).toBe("selkie");
    expect(speciesText(card("Bren", []))).toBe("");
    // several side by side: a half-selkie
    expect(speciesText(card("Ash", [rel("is a", ref("selkie")), rel("is a", ref("human"))]))).toBe("selkie · human");
    // not for other kinds, and only species on the other side
    expect(speciesText(card("Guild", [rel("is a", ref("selkie"))], "faction"))).toBe("");
    expect(speciesText(card("Bren", [rel("is a", ref("Lamp Guild", "faction"))]))).toBe("");
  });

  it("puts it on the name's card, with who possesses them, leaving those out of the list", () => {
    const isolde = card("Isolde", [rel("possessed by", ref("the Grey Tenant", "character"), "c10", "c13"), rel("member of", ref("The Lamp Guild", "faction"))]);
    isolde.relations[1]!.role = "Captain";
    expect(possessors(asOf(isolde, "c13")).map((p) => p.name)).toEqual(["the Grey Tenant"]);
    expect(possessors(asOf(isolde, "c5"))).toEqual([]);
    const dom = cardDom(asOf(isolde, "c13"), { open: () => {} });
    expect(dom.querySelector(".qcard-possessed")?.textContent).toBe("possessed by the Grey Tenant");
    expect([...dom.querySelectorAll(".qcard-rels li")].map((li) => li.textContent)).toEqual(["member of The Lamp Guild · Captain"]);
    const s = cardDom(asOf(seyla, "c5"), { open: () => {} });
    expect(s.querySelector(".qcard-species")?.textContent).toBe("selkie · appears as human");
    expect(s.textContent).not.toContain("is a selkie");
  });
});

describe("the characters table's Species column", () => {
  const cards = [seyla, card("Varren", [rel("is a", ref("human"), null, "c9"), rel("is a", ref("wraith"), "c10")]), card("Bren", [])];
  const reader: LabelReader = { several: () => false, last: order.length - 1, indexOf };
  it("reads what each is at the end of the story", () => {
    expect(speciesAtEnd(cards[1]!, order.length - 1, indexOf)).toEqual(["wraith"]);
    expect(speciesAtEnd(cards[1]!, null, indexOf)).toEqual(["human", "wraith"]);
    expect(valuesAtEnd(seyla, SPECIES_COLUMN, true, order.length - 1, indexOf)).toEqual(["selkie"]);
  });
  it("filters and groups like a fact column", () => {
    expect(cards.filter((c) => matches(c, [{ label: SPECIES_COLUMN, value: "Selkie" }], reader)).map((c) => c.name)).toEqual(["Seyla"]);
    expect(groupBy(cards, (c) => c, SPECIES_COLUMN, reader).map((g) => [g.value, g.items.map((c) => c.name)])).toEqual([
      ["selkie", ["Seyla"]],
      ["wraith", ["Varren"]],
      [null, ["Bren"]],
    ]);
  });
});

describe("the graph coloured by species", () => {
  const data = {
    nodes: [ref("Seyla", "character"), ref("Ash", "character"), ref("Varren", "character"), ref("Bren", "character"), ref("selkie"), ref("human")],
    edges: [
      { a: "Seyla", b: "selkie", label: "is a", reverse_label: "includes", standing: "canon", from_chapter_id: null, until_chapter_id: null },
      { a: "Ash", b: "selkie", label: "is a", reverse_label: "includes", standing: "canon", from_chapter_id: null, until_chapter_id: null },
      { a: "Varren", b: "human", label: "is a", reverse_label: "includes", standing: "canon", from_chapter_id: "c3", until_chapter_id: null },
    ],
  };
  it("gives each species a colour in order of size, as of a chapter", () => {
    const all = speciesColours(data, null, indexOf);
    expect(all.legend.map((s) => [s.name, s.count])).toEqual([["selkie", 2], ["human", 1]]);
    expect(all.of.get("Seyla")).toBe("selkie");
    expect(all.of.has("Bren")).toBe(false);
    expect(all.legend[0]!.colour).not.toBe(all.legend[1]!.colour);
    expect(speciesColours(data, 0, indexOf).of.has("Varren")).toBe(false);
  });
});

describe("roles offered on a relationship", () => {
  it("puts the group's own roles first, then by use", () => {
    const sug = { t: [{ role: "Treasurer", count: 5, groups: ["other"] }, { role: "Captain", count: 2, groups: ["guild"] }] };
    expect(rolesFor(sug, "t", "guild").map((r) => r.role)).toEqual(["Captain", "Treasurer"]);
    expect(rolesFor(sug, "t", "else").map((r) => r.role)).toEqual(["Treasurer", "Captain"]);
    expect(rolesFor(sug, "none", "guild")).toEqual([]);
  });
});

describe("ancestor of in the family tree", () => {
  // Oswin is Mirelle's parent and Tess her child; Old Mirelle is Mirelle's ancestor, recorded, generations between not
  // known; Old Mirelle's own parent is Ancient; Old Mirelle's other line has a child Kell
  const types = [
    { id: "parent", a_kind: "character", b_kind: "character", label: "parent of", reverse_label: "child of" },
    { id: "anc", a_kind: "character", b_kind: "character", label: "ancestor of", reverse_label: "descendant of" },
  ];
  const e = (id: string, a: string, b: string, type: string) => {
    const t = types.find((x) => x.id === type)!;
    return { id, a, b, type_id: type, label: t.label, reverse_label: t.reverse_label, standing: "canon" as const, from_chapter_id: null, until_chapter_id: null };
  };
  const names = ["Mirelle", "Oswin", "Tess", "Old Mirelle", "Ancient", "Kell", "Oswin's sister"];
  const data: GraphData = {
    nodes: names.map((n) => ({ id: n, name: n, kind: "character", summary: "", gender: null, project: null })),
    edges: [
      e("1", "Oswin", "Mirelle", "parent"),
      e("2", "Mirelle", "Tess", "parent"),
      e("3", "Old Mirelle", "Mirelle", "anc"),
      e("4", "Ancient", "Old Mirelle", "parent"),
      e("5", "Old Mirelle", "Kell", "parent"),
    ],
    types,
    presence: [],
    cooccurrence: [],
  };
  const fam = new Family(familyLinks(data, { asOf: null, indexOf, standings: new Set(["canon"]) }));
  const kin = (id: string) => kinOf(fam, id).map((k) => `${kinText(k, null)}: ${k.id}`).sort();

  it("lists the ancestor as ancestor, and works out only ancestors and descendants across it", () => {
    expect(kin("Mirelle")).toEqual(["ancestor: Ancient", "ancestor: Old Mirelle", "child: Tess", "parent: Oswin"]);
    // the descendant's own descendants are the ancestor's descendants; no cousins through the lineage
    expect(kin("Old Mirelle")).toEqual(["child: Kell", "descendant: Mirelle", "descendant: Tess", "parent: Ancient"]);
    expect(kin("Tess")).toContain("ancestor: Old Mirelle");
    expect(kin("Kell").some((k) => /cousin|sibling|relative/.test(k))).toBe(false);
  });

  it("draws it as a long dashed link, the ancestor at least two rows above", () => {
    const tree = layoutTree(fam, "Mirelle", (id) => id, () => "about 600 years");
    const row = (id: string) => tree.people.find((p) => p.id === id)!.gen;
    expect(row("Mirelle") - row("Old Mirelle")).toBeGreaterThanOrEqual(2);
    const [line] = tree.lines.filter((l) => l.kind === "ancestor");
    expect(line).toMatchObject({ dashed: true, label: "about 600 years" });
    expect(layoutTree(fam, "Mirelle").lines.find((l) => l.kind === "ancestor")!.label).toBe("generations not recorded");
  });

  it("counts for their own ancestor", () => {
    const loop = new Family(familyLinks({ ...data, edges: [...data.edges, e("6", "Tess", "Old Mirelle", "parent")] }, { asOf: null, indexOf, standings: new Set(["canon"]) }));
    expect(loop.loops().length).toBe(1);
  });
});
