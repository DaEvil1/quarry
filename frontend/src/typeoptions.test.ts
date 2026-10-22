import { describe, expect, it } from "vitest";

import { typeOptions } from "./bible";
import type { RelationType } from "./types";

const t = (a_kind: string, b_kind: string, label: string, reverse_label: string | null): RelationType =>
  ({ id: label, a_kind, b_kind, label, reverse_label, position: 0, used: 0 }) as RelationType;

const TYPES = [
  t("*", "*", "linked to", null),
  t("character", "character", "parent of", "child of"),
  t("character", "character", "married to", null),
  t("character", "place", "lives in", "home of"),
];
const reads = (from: string, to: string) => typeOptions(TYPES, from, to).map((o) => `${o.reads}${o.forward ? "" : " (back)"}`);

describe("typeOptions", () => {
  it("offers both readings of a two-way type between the same kinds, and a symmetric one once", () => {
    expect(reads("character", "character")).toEqual(["parent of", "child of (back)", "married to", "linked to"]);
  });

  it("reads a type backwards from its B side", () => {
    expect(reads("place", "character")).toEqual(["home of (back)", "linked to"]);
    expect(reads("character", "place")).toEqual(["lives in", "linked to"]);
  });
});
