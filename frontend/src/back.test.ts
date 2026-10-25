// Phase 13b in the browser (docs/SPEC.md §14.4–§14.9): Lately on the front page, how long ago, the focus (where a
// world opens, where Include planned starts), cause arrows, and an entry of more than one kind.

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { includePlanned, readLastPlace, setIncludePlanned, worldTarget, writeLastPlace } from "./focus";
import { howLongAgo, lately, type LatelyEvent } from "./front";
import { homeTarget } from "./router";
import { useSession } from "./stores/session";
import type { World } from "./types";
import { useCards, kindsOf, type Card } from "./world/cards";
import { arrowPath, causeDirection, causeLinks, linksOf } from "./world/causes";

const world = (slug: string, focus: "writing" | "planning" = "writing"): World => ({
  id: slug, name: slug, slug, role: "owner", focus,
  projects: [{ id: `${slug}/p`, name: "Book", slug: "book", kind: "novel", position: 0, gap_chapters: 5 }],
});

describe("Lately", () => {
  it("groups by day, newest first, the last ten days with anything, each line counted", () => {
    const events: LatelyEvent[] = [
      { kind: "words", at: "2023-03-14T10:00:00", project: "book", n: 1000 },
      { kind: "words", at: "2023-03-14T18:00:00", project: "book", n: 240 },
      { kind: "journal", at: "2023-03-14T09:00:00", id: "j1" },
      { kind: "journal", at: "2023-03-14T11:00:00", id: "j1" },
      { kind: "journal", at: "2023-03-14T12:00:00", id: "j2" },
      { kind: "entity", at: "2023-03-14T12:00:00", id: "v", name: "Varren", entity_kind: "character", added: false },
      { kind: "fact", at: "2023-03-14T12:00:00" },
      { kind: "captured", at: "2023-03-14T13:00:00", item_kind: "question" },
      { kind: "decision", day: "2021-01-02" },
      ...Array.from({ length: 12 }, (_, i) => ({ kind: "fact" as const, at: `2020-01-${String(i + 1).padStart(2, "0")}T12:00:00` })),
    ];
    const days = lately(events);
    expect(days).toHaveLength(10);
    expect(days[0]).toMatchObject({ day: "2023-03-14", words: [{ project: "book", n: 1240 }], journal: 2, facts: 1, captured: 1 });
    expect(days[0]!.entities.map((e) => e.name)).toEqual(["Varren"]);
    expect(days[1]).toMatchObject({ day: "2021-01-02", decisions: 1 });
    expect(days[9]!.day).toBe("2020-01-05");
  });

  it("says how long ago, so a long gap is plain", () => {
    expect(howLongAgo("2026-10-25", "2026-10-25")).toBe("today");
    expect(howLongAgo("2026-10-24", "2026-10-25")).toBe("yesterday");
    expect(howLongAgo("2026-10-21", "2026-10-25")).toBe("four days ago");
    expect(howLongAgo("2026-10-04", "2026-10-25")).toBe("three weeks ago");
    expect(howLongAgo("2023-03-14", "2026-10-25")).toBe("three years ago");
  });
});

describe("the focus", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("opens a world under Planning on its front page, under Writing at the last place used", () => {
    writeLastPlace("delta", "/w/delta/chapters/c9");
    expect(readLastPlace("delta")).toBe("/w/delta/chapters/c9");
    expect(worldTarget(world("delta"))).toBe("/w/delta/chapters/c9");
    expect(worldTarget(world("delta", "planning"))).toEqual({ name: "world", params: { world: "delta" } });
    expect(worldTarget(world("other"))).toEqual({ name: "world", params: { world: "other" } });
    useSession().me = { user: { id: "u", display_name: "W" }, worlds: [world("delta", "planning")] };
    expect(homeTarget(false)).toEqual({ name: "world", params: { world: "delta" } });
    expect(homeTarget(true)).toEqual({ name: "capture", params: { world: "delta" } });
  });

  it("starts Include planned from the focus; set by hand, it stays until the focus changes", () => {
    expect(includePlanned(world("delta"))).toBe(false);
    expect(includePlanned(world("delta", "planning"))).toBe(true);
    setIncludePlanned(world("delta"), true);
    expect(includePlanned(world("delta"))).toBe(true);
    // the focus changed: it starts from the focus again
    expect(includePlanned(world("delta", "planning"))).toBe(true);
    setIncludePlanned(world("delta", "planning"), false);
    expect(includePlanned(world("delta", "planning"))).toBe(false);
    expect(includePlanned(world("delta"))).toBe(false);
  });
});

describe("cause arrows", () => {
  const node = (id: string, kind = "event") => ({ id, name: id, kind: kind as Card["kind"], summary: "" });
  const edge = (id: string, a: string, b: string, label: string, reverse: string | null, standing = "canon") =>
    ({ id, a, b, type_id: "t", label, reverse_label: reverse, standing, from_chapter_id: null, until_chapter_id: null }) as never;

  it("reads types by label, either way round, whatever the capitals", () => {
    expect(causeDirection("caused", "caused by")).toBe(1);
    expect(causeDirection("Followed From", "led to")).toBe(-1);
    expect(causeDirection("knows", null)).toBe(0);
    const g = {
      nodes: [node("founding"), node("wars"), node("burning"), node("varren", "character")],
      edges: [edge("r1", "founding", "wars", "caused", "caused by"), edge("r2", "burning", "wars", "followed from", "led to", "planned"), edge("r3", "founding", "varren", "caused", "caused by")],
    };
    const links = causeLinks(g);
    expect(links.map((l) => [l.cause, l.effect, l.standing])).toEqual([["founding", "wars", "canon"], ["wars", "burning", "planned"]]);
    expect(linksOf(links, "founding", false).map((x) => x.link.id)).toEqual(["r1"]);
    expect(linksOf(links, "founding", true).map((x) => [x.link.id, x.depth])).toEqual([["r1", 1], ["r2", 2]]);
    expect(linksOf(links, "burning", true).map((x) => [x.link.id, x.depth])).toEqual([["r2", 1], ["r1", 2]]);
  });

  it("stops a loop where it closes", () => {
    const g = { nodes: [node("a"), node("b")], edges: [edge("r1", "a", "b", "caused", null), edge("r2", "b", "a", "caused", null)] };
    expect(linksOf(causeLinks(g), "a", true)).toHaveLength(2);
  });

  it("curves above, from cause to effect", () => {
    expect(arrowPath(0, 100, 120, 100)).toBe("M 0 100 Q 60 62 120 100");
  });
});

describe("an entry of more than one kind", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("is counted under each kind and has each", () => {
    const c = (id: string, kind: Card["kind"], also: Card["kind"][] = []): Card => ({
      id, name: id, kind, aliases: [], first_name: null, match_case: true, exclusions: [], summary: "", facts: [], relations: [], also_kinds: also,
    });
    const cards = useCards();
    cards.apply({ cards: [c("ashgard", "place", ["character"]), c("varren", "character")], ignored: [] });
    expect(kindsOf(cards.byId.get("ashgard")!)).toEqual(["place", "character"]);
    expect(cards.counts).toEqual({ place: 1, character: 2 });
    expect(cards.hasKind("ashgard", "character")).toBe(true);
    expect(cards.hasKind("varren", "place")).toBe(false);
  });
});
