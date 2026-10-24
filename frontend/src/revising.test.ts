import "fake-indexeddb/auto";

import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { around, cutLabel, findPlace } from "./cuts";
import { changesLine, changesSince } from "./editor/changes";
import { localDb } from "./localdb";
import { statusStrength, type WordHistory } from "./manuscript";
import { useOutbox } from "./stores/outbox";
import { wordBars } from "./wordhistory";
import type { Card } from "./world/cards";
import { Matcher } from "./world/matcher";
import { segments, thread, threadCount, type ThreadChapter } from "./world/thread";

const card = (id: string, name: string, extra: Partial<Card> = {}): Card => ({
  id, name, kind: "character", aliases: [], first_name: null, match_case: true, exclusions: [], summary: "", facts: [], relations: [], ...extra,
});

// ---- 11.2 statuses ----

describe("status pills", () => {
  it("get stronger by position, the first faint and the last the strongest", () => {
    expect(statusStrength(0, 3)).toBe(0.25);
    expect(statusStrength(1, 3)).toBeCloseTo(0.625);
    expect(statusStrength(2, 3)).toBe(1);
    expect(statusStrength(0, 1)).toBe(1);
  });
});

// ---- 11.3 the cuts bin ----

describe("putting a cut back where it was", () => {
  const doc = "First paragraph.\n\nThe heron lifted.\n\nLast paragraph.";

  it("keeps the text either side, and finds the place again by it", () => {
    const from = doc.indexOf("The heron");
    const to = from + "The heron lifted.\n\n".length;
    const { before, after } = around(doc, from, to);
    expect(before).toBe("First paragraph.\n\n");
    expect(after).toBe("Last paragraph.");
    const left = doc.slice(0, from) + doc.slice(to);
    expect(findPlace(left, before, after)).toBe(from);
  });

  it("uses one side alone when the other was edited, and gives up when the place is gone or found twice", () => {
    const before = "the long first paragraph.\n\n";
    const after = "And then the last one.";
    expect(findPlace(`Opening, the long first paragraph.\n\nAnd then, at last, the end.`, before, after)).toBe(36);
    expect(findPlace("Something else entirely.", before, after)).toBeNull();
    expect(findPlace(`x ${before}${after} y ${before}${after}`, before, after)).toBeNull();
    expect(findPlace("", "", "")).toBe(0);
  });

  it("says how many words went to the bin", () => {
    expect(cutLabel(84)).toBe("Cut 84 words to the bin");
    expect(cutLabel(1)).toBe("Cut 1 word to the bin");
  });
});

describe("cuts in the outbox", () => {
  const json = (status: number, body: unknown) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  beforeEach(async () => {
    setActivePinia(createPinia());
    await localDb.outbox.clear();
    await localDb.pendingCuts.clear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("waits on the device while offline, with its own id, and is sent when back", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    const outbox = useOutbox();
    const cut = { id: "c1", world: "coast", chapterId: "ch1", body: "The heron lifted.", before: "a", after: "b" };
    expect(await outbox.addCut(cut)).toBe(false);
    expect(outbox.waiting).toBe(1);

    const sent: { url: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string, init: RequestInit) => {
      sent.push({ url, body: JSON.parse(String(init.body)) });
      return Promise.resolve(json(201, {}));
    }));
    await outbox.send();
    expect(sent).toEqual([{ url: "/api/worlds/coast/cuts", body: expect.objectContaining({ id: "c1", chapter_id: "ch1", body: "The heron lifted.", before: "a", after: "b" }) }]);
    expect(outbox.waiting).toBe(0);
  });

  it("an undo before it was sent just drops it", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    const outbox = useOutbox();
    await outbox.addCut({ id: "c2", world: "coast", chapterId: "ch1", body: "x", before: "", after: "" });
    expect(await outbox.dropCut("c2")).toBe(true);
    expect(outbox.cuts).toEqual([]);
    expect(await outbox.dropCut("c2")).toBe(false);
  });
});

// ---- 11.4 reading one entry's thread ----

describe("reading one entry's thread", () => {
  const matcher = new Matcher([
    card("v", "Varren Hale", { aliases: ["the Grey Keeper"], first_name: "Varren" }),
    card("i", "Isolde"),
    card("h", "Old Harbour", { kind: "place" }),
  ]);
  const ch = (id: string, body: string, state: ThreadChapter["state"] = "current"): ThreadChapter => ({
    id, title: id, body, state, project: "one", project_name: "One",
  });
  const chapters = [
    ch("c1", "Varren waits.\n\nThe boat comes.\n\nRain.\n\nThe Grey Keeper climbs to Old Harbour.\n%% check his age here"),
    ch("c2", "Nobody here."),
    ch("c3", "%% Varren and Isolde should meet sooner\nIsolde sings.\n\nVarren Hale listens to Isolde."),
  ];

  it("keeps the paragraphs that name him by any of his names, with the margin notes beside them, and gaps between", () => {
    const r = thread(chapters, matcher, ["v"], "paragraphs");
    expect(threadCount(["Varren Hale"], r.paragraphs, r.chapters)).toBe("Varren Hale: 4 paragraphs in 2 chapters");
    const [first, third] = r.parts;
    expect(first!.blocks.map((b) => (b.kind === "gap" ? `⋯${b.paras.length}` : b.text))).toEqual([
      "Varren waits.", "⋯2", "The Grey Keeper climbs to Old Harbour.", "%% check his age here"]);
    // a margin note that names him is a hit of its own; the next paragraph doesn't name him, so it is left out
    expect(third!.blocks.map((b) => (b.kind === "para" ? [b.text, b.hit, b.margin] : "gap"))).toEqual([
      ["%% Varren and Isolde should meet sooner", true, true], "gap", ["Varren Hale listens to Isolde.", true, false]]);
  });

  it("with a second entry, only what names both", () => {
    const r = thread(chapters, matcher, ["v", "i"], "paragraphs");
    expect(threadCount(["Varren Hale", "Isolde"], r.paragraphs, r.chapters)).toBe("Varren Hale and Isolde: 2 paragraphs in 1 chapter");
    const byChapter = thread(chapters, matcher, ["v", "i"], "chapters");
    expect(byChapter.parts.map((p) => p.chapter.id)).toEqual(["c3"]);
    expect(thread(chapters, matcher, ["v"], "chapters").parts.map((p) => p.chapter.id)).toEqual(["c1", "c3"]);
  });

  it("cuts a paragraph into text and names for colouring", () => {
    const r = thread([chapters[0]!], matcher, ["v"], "paragraphs");
    const p = r.parts[0]!.blocks[2]!;
    if (p.kind !== "para") throw new Error("expected a paragraph");
    expect(segments(p).map((s) => [s.text, s.hit?.entityId ?? null])).toEqual([
      ["The Grey Keeper", "v"], [" climbs to ", null], ["Old Harbour", "h"], [".", null]]);
  });
});

// ---- 11.5 word history ----

describe("word history", () => {
  const now = new Date(2026, 9, 24, 15, 0);
  const at = (d: number, h = 10) => new Date(2026, 9, d, h, 0).toISOString();
  const h: WordHistory = {
    revisions: [
      { at: at(22), chapter_id: "a", added: 300, removed: 10 },
      { at: at(22, 20), chapter_id: "b", added: 200, removed: 0 },
      { at: at(23), chapter_id: "a", added: 5, removed: 400 },
    ],
    pending: [{ chapter_id: "b", added: 40, removed: 2 }],
    chapters: { a: "One", b: "Two" },
  };

  it("sums each day's revisions in the browser's time zone, with today's unsaved work", () => {
    const { bars, written, cut } = wordBars(h, "weeks", now);
    expect(bars).toHaveLength(56);
    const last3 = bars.slice(-3).map((b) => [b.written, b.cut, b.chapters]);
    expect(last3).toEqual([[500, 10, ["One", "Two"]], [5, 400, ["One"]], [40, 2, ["Two"]]]);
    expect([written, cut]).toEqual([545, 412]);
    // nothing judged: a day without writing is just zero
    expect(bars[0]).toMatchObject({ written: 0, cut: 0, chapters: [] });
  });

  it("by week over a year, and by month over everything", () => {
    expect(wordBars(h, "year", now).bars).toHaveLength(52);
    expect(wordBars(h, "year", now).bars.at(-1)).toMatchObject({ written: 545, cut: 412 });
    const months = wordBars({ ...h, revisions: [...h.revisions, { at: new Date(2026, 6, 3).toISOString(), chapter_id: "a", added: 7, removed: 0 }] }, "all", now);
    expect(months.bars.map((b) => b.written)).toEqual([7, 0, 0, 545]);
  });
});

// ---- 11.6 changes since a checkpoint ----

describe("changes since a checkpoint", () => {
  it("tints changed words, marks removed passages, and counts them", () => {
    const base = "The boat comes in at dawn.\n\nA gull cries. The rain stops.\n\nThe end.";
    const now = "The small boat comes in at dawn.\n\nA gull cries.\n\nThe end.";
    const c = changesSince(base, now);
    const shown = c.changes.map((x) => [now.slice(x.from, x.to), x.was.trim()]);
    expect(shown).toEqual([["small ", ""], ["", "The rain stops."]]);
    expect(changesLine(c, "before the polish")).toBe("1 word changed, 1 passage removed since “before the polish”");
  });

  it("marks a new paragraph whole, and finds nothing when nothing changed", () => {
    const base = "One.\n\nTwo.";
    const c = changesSince(base, "One.\n\nNew here.\n\nTwo.");
    expect(c.changes.map((x) => "One.\n\nNew here.\n\nTwo.".slice(x.from, x.to))).toEqual(["New here."]);
    expect(c.words).toBe(2);
    expect(changesSince(base, base).changes).toEqual([]);
  });

  it("a changed word keeps what was there, for resting on it", () => {
    const c = changesSince("Varren waits.", "Varran waits.");
    expect(c.changes).toEqual([{ from: 0, to: 6, was: "Varren" }]);
    expect(c.removed).toBe(0);
  });
});
