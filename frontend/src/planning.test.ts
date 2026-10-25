// Phase 13a in the browser (docs/SPEC.md §14.1–§14.3): loose-end markers, items made from a passage, the planning
// reading, the journal mode of the companion, and the saver with a journal entry.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AUTOSAVE_MS, ChapterSaver } from "./editor/saver";
import { itemBody } from "./editor/passage";
import { EntryConflict, originLine } from "./journal";
import type { JournalDetail } from "./types";
import type { Card } from "./world/cards";
import { analyse } from "./world/findings";
import { markers } from "./world/markers";
import { Matcher } from "./world/matcher";
import { planningCount, planningReading, type PlanningEntry } from "./world/planning";

const card = (id: string, name: string, kind: Card["kind"] = "character"): Card => ({
  id, name, kind, aliases: [], first_name: null, match_case: true, exclusions: [], summary: "", facts: [], relations: [],
});
const varren = card("v", "Varren");
const isolde = card("i", "Isolde");
const guild = card("g", "the Lamp Guild", "faction");
const matcher = new Matcher([varren, isolde, guild]);

describe("loose-end markers", () => {
  it("finds TK and ?? not after a letter, with their lines", () => {
    const text = "Varren's age ?? maybe 40\nWho lit it (??)\n???\nWhat?? she said.\nTK the name";
    expect(markers(text).map((m) => [m.kind, m.line])).toEqual([
      ["??", "Varren's age ?? maybe 40"],
      ["??", "Who lit it (??)"],
      ["??", "???"],
      ["tk", "TK the name"],
    ]);
    expect(markers("a single ? and TKO")).toEqual([]);
  });

  it("are findings in a chapter and in a journal entry, where %% lines are ordinary text", () => {
    const base = { matcher, card: () => undefined, linked: new Set<string>(), presence: [], resolved: new Set<string>(), longSentence: 0 };
    const chapter = analyse({ ...base, text: "%% a note ??\nVarren's age ?? maybe" });
    expect(chapter.filter((f) => f.editor === "looseEnds").map((f) => f.rule)).toEqual(["unsure", "margin"]);
    const journal = analyse({ ...base, text: "%% a note ??\nVarren's age ?? maybe", journal: true });
    expect(journal.filter((f) => f.editor === "looseEnds").map((f) => f.rule)).toEqual(["unsure", "unsure"]);
  });

  it("in a journal entry there is no Where are they?", () => {
    const harbour = card("h", "Old Harbour", "place");
    const lamp = card("l", "Lamphouse", "place");
    const m = new Matcher([varren, harbour, lamp]);
    const base = { matcher: m, card: (id: string) => [varren, harbour, lamp].find((c) => c.id === id), linked: new Set<string>(), presence: [], resolved: new Set<string>(), longSentence: 0 };
    const text = "Varren walked from Old Harbour to the Lamphouse.";
    expect(analyse({ ...base, text }).some((f) => f.rule === "where")).toBe(true);
    expect(analyse({ ...base, text, journal: true }).some((f) => f.rule === "where")).toBe(false);
  });
});

describe("an item made from a passage", () => {
  it("is your line followed by the passage as a quote, or just the quote", () => {
    expect(itemBody("Who lit it?", "the Lamp lit\nfor years")).toBe("Who lit it?\n\n> the Lamp lit\n> for years");
    expect(itemBody("  ", "the Lamp lit")).toBe("> the Lamp lit");
  });

  it("says where it came from", () => {
    expect(originLine({ table: "journal", id: "j", title: "What the Guild wants", date: "2019-03-02", passage: null })).toMatch(/^From the Journal, .*2019/);
    expect(originLine({ table: "chapter", id: "c", title: "The Quay", date: null, passage: null })).toBe("From the chapter “The Quay”");
  });
});

describe("the planning reading", () => {
  const entries: PlanningEntry[] = [
    { id: "j19", entry_date: "2019-03-02", title: "What the Guild wants", body: "The Lamp Guild wants the light.\nVarren knows it; Isolde doesn't.\nRain.\nVarren again.", project: null },
    { id: "j14", entry_date: "2014-05-01", title: "First thoughts", body: "Varren keeps the light.", project: "salt-road" },
    { id: "jx", entry_date: "2020-01-01", title: "Other book", body: "Varren elsewhere.", project: "other" },
  ];
  const items = [
    { id: "q", kind: "question", status: "open", title: null, body: "How old is the keeper?", closed_note: null, created_at: "2016-06-01T10:00:00Z", project: null, names: [], tagged: ["v"] },
  ];
  const decisions = [{ id: "d", decided_on: "2019-03-02", text: "Varren stays", project: null, names: ["v"], tagged: [] }];
  const read = (extra: Partial<Parameters<typeof planningReading>[0]> = {}) =>
    planningReading({ entries, items, decisions, matcher, ids: ["v"], mode: "paragraphs", kinds: new Set(["journal", "item", "decision"]), ...extra });

  it("lists sources oldest first, with a heading per year and the years between", () => {
    const r = read();
    expect(r.lines.map((l) => (l.kind === "year" ? l.year : l.kind === "gap-years" ? `· ${l.years} ·` : l.kind === "journal" ? l.entry.id : l.kind))).toEqual([
      2014, "j14", "· 2 ·", 2016, "item", "· 2 ·", 2019, "j19", "decision", 2020, "jx",
    ]);
    expect(planningCount(["Varren"], r.counts)).toBe("Varren in the planning: 4 paragraphs in 3 journal entries, 1 item, 1 decision · 2014–2020");
  });

  it("shows only the paragraphs that name the entry, with gaps, and marks an item that is only tagged", () => {
    const j19 = read().lines.find((l) => l.kind === "journal" && l.entry.id === "j19");
    expect(j19 && j19.kind === "journal" ? j19.blocks.map((b) => (b.kind === "gap" ? `⋯ ${b.paras.length}` : b.text)) : []).toEqual([
      "Varren knows it; Isolde doesn't.", "⋯ 1", "Varren again.",
    ]);
    const item = read().lines.find((l) => l.kind === "item");
    expect(item && item.kind === "item" && item.tagged).toBe(true);
  });

  it("reads whole entries, keeps only what names both, filters by project and kind, and starts from a date", () => {
    const whole = read({ mode: "entries" }).lines.find((l) => l.kind === "journal" && l.entry.id === "j19");
    expect(whole && whole.kind === "journal" ? whole.blocks.length : 0).toBe(4);
    const both = read({ ids: ["v", "i"] });
    expect(both.lines.filter((l) => l.kind !== "year" && l.kind !== "gap-years").map((l) => l.kind)).toEqual(["journal"]);
    const salt = read({ project: "salt-road" });
    expect(salt.counts.entries).toBe(2);
    expect(read({ kinds: new Set(["decision"]) }).counts).toMatchObject({ entries: 0, items: 0, decisions: 1 });
    expect(read({ from: "2019-01-01" }).counts).toMatchObject({ entries: 2, items: 0, decisions: 1 });
  });
});

describe("the saver with a journal entry", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  const entry = (version: number, body: string, title: string | null = null) =>
    ({ id: "j", version, body, title, entry_date: "2019-03-02", project: null, created_at: "", updated_at: "", mentions: [] }) as JournalDetail;

  it("keeps this device's text as a conflict copy and takes the newer entry", async () => {
    const conflicts: string[] = [];
    const snapshots: unknown[] = [];
    const saver = new ChapterSaver<JournalDetail>({ version: 1 }, {
      save: async () => {
        throw new EntryConflict(entry(3, "theirs"));
      },
      snapshot: async (r, extra) => void snapshots.push([r, extra]),
      now: () => Date.now(),
    }, { saved: () => {}, conflict: (c, mine) => void conflicts.push(`${c.body}|${mine}`), status: () => {} });
    saver.edit({ body: "mine" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS);
    expect(snapshots).toEqual([["conflict", { body: "mine" }]]);
    expect(conflicts).toEqual(["theirs|mine"]);
    expect(saver.currentVersion).toBe(3);
  });

  it("a retry the server already has counts as saved, an untitled entry included", async () => {
    const saved: number[] = [];
    const saver = new ChapterSaver<JournalDetail>({ version: 1 }, {
      save: async () => {
        throw new EntryConflict(entry(2, "same", null));
      },
      snapshot: async () => undefined,
      now: () => Date.now(),
    }, { saved: (d) => void saved.push(d.version), conflict: () => {}, status: () => {} });
    saver.edit({ body: "same", title: "" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS);
    expect(saved).toEqual([2]);
  });
});
