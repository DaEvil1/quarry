import { describe, expect, it } from "vitest";

import type { Card } from "./world/cards";
import { Matcher, osa } from "./world/matcher";

const card = (name: string, extra: Partial<Card> = {}): Card => ({
  id: name,
  name,
  kind: "character",
  aliases: [],
  first_name: null,
  match_case: true,
  exclusions: [],
  summary: "",
  facts: [],
  relations: [],
  ...extra,
});

const hits = (m: Matcher, text: string) => m.scan(text).map((h) => [h.matched, h.kind, h.entityId]);

// the same cases as backend/tests/test_mentions.py, so the browser and the server agree
describe("Matcher (same rules as the server)", () => {
  const varren = card("Varren", { aliases: ["the Grey Keeper"] });
  const harbour = card("Old Harbour", { kind: "place" });
  const isolde = card("Isolde");
  const mordoch = card("Mordoch");
  const m = new Matcher([varren, harbour, isolde, mordoch]);

  it("finds names with endings", () => {
    expect(hits(m, "Varren walked. The Varrens argued. Varren's lamp, Varren’s boat.")).toEqual([
      ["Varren", "exact", "Varren"],
      ["Varrens", "exact", "Varren"],
      ["Varren's", "exact", "Varren"],
      ["Varren’s", "exact", "Varren"],
    ]);
  });

  it("finds other names and multi-word names, and gives the kind", () => {
    const found = m.scan("They met the Grey Keeper at Old Harbour.");
    expect(found.map((h) => [h.matched, h.kind, h.entityKind])).toEqual([
      ["the Grey Keeper", "alias", "character"],
      ["Old Harbour", "exact", "place"],
    ]);
    expect(found[1].start).toBe(28);
  });

  it("respects word boundaries and capitals", () => {
    expect(hits(m, "Varrenholm is far. varren is lowercase.")).toEqual([]);
  });

  it("flags likely misspellings", () => {
    expect(hits(m, "Isolda wrote to Modroch and Varen.")).toEqual([
      ["Isolda", "near_miss", "Isolde"],
      ["Modroch", "near_miss", "Mordoch"],
      ["Varen", "near_miss", "Varren"],
    ]);
    expect(hits(m, "Isle. Harbour lights. Ocean. Thursday.")).toEqual([]);
    expect(hits(new Matcher([isolde], ["Isolda"]), "Isolda")).toEqual([]);
  });

  it("capitals optional, first names, not in this sense", () => {
    const rose = card("Rose", { match_case: false, exclusions: ["rose garden"] });
    const hale = card("Varren Hale", { first_name: "Varren" });
    const mm = new Matcher([rose, hale]);
    expect(hits(mm, "rose in the rose garden; Varren and VARREN HALE")).toEqual([
      ["rose", "exact", "Rose"],
      ["Varren", "alias", "Varren Hale"],
    ]);
  });

  it("an offset shifts positions (scanning part of a document)", () => {
    expect(m.scan("x Varren", 100)[0].start).toBe(102);
  });

  it("scanLine remembers a line and gives the same hits as scan, at any offset", () => {
    const text = "Varen met Isolde. Modroch watched.";
    expect(m.scanLine(text, 40)).toEqual(m.scan(text, 40));
    expect(m.scanLine(text, 7)).toEqual(m.scan(text, 7));
    expect(m.scanLine(text, 0, false)).toEqual(m.scan(text, 0, false));
  });

  it("a misspelling equally close to two names goes to the one met first, as on the server", () => {
    const a = card("Karran");
    const b = card("Barren");
    expect(hits(new Matcher([a, b]), "Barran")).toEqual([["Barran", "near_miss", "Karran"]]);
    expect(hits(new Matcher([b, a]), "Barran")).toEqual([["Barran", "near_miss", "Barren"]]);
  });
});

describe("osa", () => {
  it("counts a swapped pair as one edit", () => {
    expect(osa("Modroch", "Mordoch")).toBe(1);
    expect(osa("Quasiata", "Quasita")).toBe(1);
    expect(osa("abc", "abc")).toBe(0);
    expect(osa("Mountains", "Isolde", 2)).toBe(3);
  });
});
