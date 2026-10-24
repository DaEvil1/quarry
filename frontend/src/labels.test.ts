import { describe, expect, it } from "vitest";

import type { Card } from "./world/cards";
import { analyse } from "./world/findings";
import { groupBy, labelsOfKind, matches, missingKey, missingLabels, parseFilter, valuesAtEnd, type LabelReader } from "./world/labels";
import { Matcher } from "./world/matcher";
import { factsAsOf } from "./world/time";

// Phase 11 §12.6: labels and values, worked out in the browser from the cards.
const order = ["c1", "c2", "c3"];
const indexOf = (id: string | null) => (id && order.includes(id) ? order.indexOf(id) : undefined);
type F = Card["facts"][number];
const fact = (label: string, value: string, from: string | null = null, until: string | null = null): F => ({ label, value, from, until });
const card = (id: string, kind: Card["kind"], facts: F[], extra: Partial<Card> = {}): Card => ({
  id, name: id, kind, aliases: [], first_name: null, match_case: true, exclusions: [], summary: "x", facts, relations: [], ...extra,
});

const events = [
  card("Lantern Night", "event", [fact("type", "Festival")]),
  card("Spring Fair", "event", [fact("Type", "festival ")]),
  card("Ash Fair", "event", [fact("type", "Festival")]),
  card("Toll Day", "event", [fact("type", "Feast"), fact("type", "Festival", "c2")]),
  card("The Siege", "event", [fact("type", "Battle")]),
  card("The Rout", "event", [fact("type", "Battle")]),
  card("The Quiet", "event", []),
  card("Harbour", "place", [fact("type", "City")]),
];
const reader = (several: string[] = []): LabelReader => ({ several: (kind, label) => several.includes(`${kind}|${label.toLowerCase()}`), last: 2, indexOf });

describe("labels and values", () => {
  it("done when: Festival filters the events' table, and Group by type gives Festival, Battle and no type with counts", () => {
    const r = reader();
    const ev = events.filter((c) => c.kind === "event");
    // the value at the end of the story: Toll Day was a feast, then a festival from chapter 2
    expect(valuesAtEnd(events[3]!, "type", false, 2, indexOf)).toEqual(["Festival"]);
    const festivals = ev.filter((c) => matches(c, [parseFilter("type:Festival")!], r)).map((c) => c.id);
    expect(festivals).toEqual(["Lantern Night", "Spring Fair", "Ash Fair", "Toll Day"]);
    const groups = groupBy(ev, (c) => c, "type", r);
    expect(groups.map((g) => [g.value, g.items.length])).toEqual([["Festival", 4], ["Battle", 2], [null, 1]]);
    // two chips narrow further; a place's type is never an event's
    expect(ev.filter((c) => matches(c, [{ label: "type", value: "festival" }, { label: "type", value: "battle" }], r))).toEqual([]);
    expect(labelsOfKind(events, "event")).toEqual([{ label: "type", count: 6 }]);
  });

  it("a label with several values puts the entry in each group, and a filter matches any of them", () => {
    const varren = card("Varren", "character", [fact("eye colour", "green", "c1"), fact("eye colour", "red", "c1")]);
    const isolde = card("Isolde", "character", [fact("eye colour", "grey")]);
    const off = reader();
    const on = reader(["character|eye colour"]);
    expect(valuesAtEnd(varren, "eye colour", false, 2, indexOf)).toEqual(["red"]);
    expect(valuesAtEnd(varren, "eye colour", true, 2, indexOf)).toEqual(["green", "red"]);
    expect(matches(varren, [{ label: "eye colour", value: "green" }], on)).toBe(true);
    expect(matches(varren, [{ label: "eye colour", value: "green" }], off)).toBe(false);
    expect(groupBy([varren, isolde], (c) => c, "eye colour", on).map((g) => [g.value, g.items.map((c) => c.id)])).toEqual([
      ["green", ["Varren"]], ["grey", ["Isolde"]], ["red", ["Varren"]]]);
  });

  it("done when (12.6.4): as of keeps every value of a several-values label; off, the latest takes over", () => {
    const facts = [fact("eye colour", "green", "c1"), fact("eye colour", "red", "c1"), fact("status", "alive"), fact("status", "dead", "c2")]
      .map((f) => ({ ...f, from_chapter_id: f.from, until_chapter_id: f.until }));
    const several = (label: string) => label === "eye colour";
    expect(factsAsOf(facts, 2, indexOf, several).map((f) => f.value)).toEqual(["green", "red", "dead"]);
    expect(factsAsOf(facts, 2, indexOf).map((f) => f.value)).toEqual(["red", "dead"]);
  });

  it("expected labels an entry is missing, whatever its standing or capitals", () => {
    const c = card("Varren", "character", [fact("Eye Colour", "green")], { labels: ["eye colour", "age"] });
    expect(missingLabels(c, ["eye colour", "age", "voice"])).toEqual(["voice"]);
    expect(missingKey("v1", "Eye  Colour")).toBe("v1:eye colour");
  });
});

describe("the Archivist's findings for phase 11", () => {
  const cards = [
    card("v", "character", [], { name: "Varren", labels: [] }),
    card("i", "character", [], { name: "Isolde", labels: ["eye colour"] }),
    card("m", "character", [], { name: "Mirelle", project: "the-salt-road", labels: ["eye colour"] }),
    card("s", "character", [], { name: "Seyla", labels: [] }),
  ];
  const byId = new Map(cards.map((c) => [c.id, c]));
  const run = (text: string, extra: { resolved?: Set<string>; project?: string; expected?: string[] } = {}) =>
    analyse({
      text,
      matcher: new Matcher(cards),
      card: (id) => byId.get(id),
      linked: new Set(["i:v", "m:v", "i:m"].map((k) => k)),
      presence: [],
      resolved: extra.resolved ?? new Set(),
      longSentence: 0,
      project: extra.project ?? "ninefold",
      projectName: (slug) => (slug === "the-salt-road" ? "The Salt Road" : slug),
      expected: (kind) => (kind === "character" ? (extra.expected ?? []) : []),
    }).filter((f) => f.editor === "archivist");

  it("done when: an expected label makes the Archivist list a named character without it; not for this one silences it", () => {
    expect(run("Varren and Isolde.").filter((f) => f.rule === "missing_label")).toEqual([]);
    const found = run("Varren and Isolde.", { expected: ["eye colour"] }).filter((f) => f.rule === "missing_label");
    expect(found.map((f) => [f.message, f.key, f.label])).toEqual([["Varren has no eye colour (expected for characters).", "v:eye colour", "eye colour"]]);
    // a character not named in the chapter isn't listed; a resolved one never comes back
    expect(found.some((f) => f.a?.name === "Seyla")).toBe(false);
    expect(run("Varren and Isolde.", { expected: ["eye colour"], resolved: new Set(["missing_label|v:eye colour"]) }).filter((f) => f.rule === "missing_label")).toEqual([]);
  });

  it("done when: naming a Salt Road entry in a Ninefold chapter offers Share with the world", () => {
    const f = run("Mirelle came to the quay.").find((x) => x.rule === "crossover")!;
    expect(f.message).toBe("Mirelle is in The Salt Road's bible and is named here.");
    expect(f.key).toBe("m:ninefold");
    expect(run("Mirelle came to the quay.", { project: "the-salt-road" }).some((x) => x.rule === "crossover")).toBe(false);
    expect(run("Mirelle came.", { resolved: new Set(["crossover|m:ninefold"]) }).some((x) => x.rule === "crossover")).toBe(false);
  });
});
