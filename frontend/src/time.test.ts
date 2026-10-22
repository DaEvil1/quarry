import { describe, expect, it } from "vitest";

import { factsAsOf, holds, spanText } from "./world/time";

const order = ["c1", "c2", "c3", "c9"];
const indexOf = (id: string | null) => (id ? (order.indexOf(id) >= 0 ? order.indexOf(id) : undefined) : undefined);
const f = (label: string, value: string, from: string | null = null, until: string | null = null) => ({
  label,
  value,
  from_chapter_id: from,
  until_chapter_id: until,
});

describe("story time", () => {
  it("a span holds from its first chapter through its last", () => {
    expect(holds(f("x", "y", "c2", "c3"), 0, indexOf)).toBe(false);
    expect(holds(f("x", "y", "c2", "c3"), 1, indexOf)).toBe(true);
    expect(holds(f("x", "y", "c2", "c3"), 2, indexOf)).toBe(true);
    expect(holds(f("x", "y", "c2", "c3"), 3, indexOf)).toBe(false);
    expect(holds(f("x", "y"), 3, indexOf)).toBe(true);
  });

  it("dead from chapter 9 takes over from alive", () => {
    const facts = [f("status", "alive"), f("eyes", "grey"), f("Status", "dead", "c9")];
    expect(factsAsOf(facts, 2, indexOf).map((x) => x.value)).toEqual(["alive", "grey"]);
    expect(factsAsOf(facts, 3, indexOf).map((x) => x.value)).toEqual(["grey", "dead"]);
  });

  it("a chapter that left the story doesn't bound a span", () => {
    expect(holds(f("x", "y", "gone"), 0, indexOf)).toBe(true);
  });

  it("reads a span", () => {
    const title = (id: string) => ({ c1: "Arrival", c3: "Storm" })[id];
    expect(spanText(f("x", "y", "c1", "c3"), title)).toBe("Arrival – Storm");
    expect(spanText(f("x", "y", "c3"), title)).toBe("from Storm");
    expect(spanText(f("x", "y", null, "c1"), title)).toBe("until Arrival");
    expect(spanText(f("x", "y", "c1", "c1"), title)).toBe("in Arrival");
    expect(spanText(f("x", "y"), title)).toBe("");
  });
});
