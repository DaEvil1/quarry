// Names shared by two entries in the browser (docs/SPEC.md §14.10): the editor's choice lines and its "From here"
// strip, the thread readings, the cast, the mentions strip and the companion's findings. The matcher's own cases (the
// same table as the server's) are in matcher.test.ts.

import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";

import { choicesOf, choiceOn, choicesField, chooseChange, matcherFacet, namesChanged, settle } from "./editor/shared";
import { badChoiceStripDom, settledRow, sharedCardDom } from "./editor/strips";
import type { Mention, StoryChapter } from "./types";
import type { Card } from "./world/cards";
import { castOf, shortNames } from "./world/cast";
import { analyse, linkKey } from "./world/findings";
import { Matcher } from "./world/matcher";
import { planningReading } from "./world/planning";
import { mentionStrip } from "./world/strip";
import { thread, unsettledLine, type ThreadChapter } from "./world/thread";

const card = (id: string, name: string, extra: Partial<Card> = {}): Card => ({
  id, name, kind: "character", aliases: [], first_name: null, match_case: true, exclusions: [], summary: "", facts: [], relations: [], ...extra,
});
const marr = card("marr", "Isolde Marr", { first_name: "Isolde", summary: "Keeps the lamp at Old Harbour." });
const senn = card("senn", "Isolde Senn", { first_name: "Isolde", summary: "A ferry pilot." });
const varren = card("varren", "Varren Hale");
const harbour = card("harbour", "Old Harbour", { kind: "place" });
const cards = [marr, senn, varren, harbour];
const byId = new Map(cards.map((c) => [c.id, c]));
const matcher = new Matcher(cards);

const stateOf = (doc: string, m: Matcher = matcher) => EditorState.create({ doc, extensions: [matcherFacet.of(() => m), choicesField] });
/** What the editor colours on each line: the name, its kind and who it is. */
function coloured(state: EditorState): [string, string, string][] {
  const out: [string, string, string][] = [];
  for (let n = 1; n <= state.doc.lines; n++) {
    const line = state.doc.line(n);
    if (choiceOn(state, line.from)) continue;
    for (const h of settle(state, matcher, matcher.scanLine(line.text, line.from, false))) out.push([h.matched, h.kind, (h.chosen ?? [h.entityId]).join("+")]);
  }
  return out;
}

describe("the editor's choice lines", () => {
  it("done when: ambiguous before a choice, the choice's entry after it, and Unsure makes it ambiguous again", () => {
    const s = stateOf("Isolde came to the quay.\n%% Isolde: Marr\nIsolde's lamp.\n%% Isolde: Marr, Senn\nIsolde.\n%% Isolde: ?\nIsolde slept.");
    expect(coloured(s)).toEqual([
      ["Isolde", "ambiguous", "marr"], ["Isolde's", "alias", "marr"], ["Isolde", "alias", "marr+senn"], ["Isolde", "ambiguous", "marr"],
    ]);
  });

  it("keeps the choice lines in step with typing elsewhere, and finds them again when a %% line changes", () => {
    let s = stateOf("Isolde came.\n%% Isolde: Senn\nIsolde sang.");
    const before = choicesOf(s);
    s = s.update({ changes: { from: 0, insert: "At dusk, " } }).state;
    expect(choicesOf(s)[0]).toMatchObject({ start: before[0]!.start + 9, ids: ["senn"] });
    expect(coloured(s).map(([, k, id]) => `${k}:${id}`)).toEqual(["ambiguous:marr", "alias:senn"]);
    // the line rewritten by hand
    const line = s.doc.line(2);
    s = s.update({ changes: { from: line.from, to: line.to, insert: "%% Isolde: Marr" } }).state;
    expect(coloured(s)[1]).toEqual(["Isolde", "alias", "marr"]);
    // a new %% line typed above
    s = s.update({ changes: { from: 0, insert: "%% Isolde: Senn\n" } }).state;
    expect(coloured(s)[0]).toEqual(["Isolde", "alias", "senn"]);
  });

  it("finds them again when the names change (a name no longer shared: an ordinary margin note)", () => {
    const one = new Matcher([marr, varren]);
    let s = stateOf("%% Isolde: Marr\nIsolde.", matcher);
    expect(choicesOf(s)).toHaveLength(1);
    s = EditorState.create({ doc: s.doc, extensions: [matcherFacet.of(() => one), choicesField] });
    expect(choicesOf(s)).toEqual([]);
    expect(s.update({ effects: namesChanged.of(null) }).state.field(choicesField)).toEqual([]);
  });

  it("From here inserts a line above the paragraph, and rewrites it when it is already there", () => {
    let s = stateOf("Varren waited.\n\nIsolde came to the quay.");
    const para = s.doc.line(3).from;
    s = s.update({ changes: chooseChange(s, para, "isolde", "Isolde", ["Isolde Marr"]) }).state;
    expect(s.doc.toString()).toBe("Varren waited.\n\n%% Isolde: Isolde Marr\nIsolde came to the quay.");
    expect(coloured(s).at(-1)).toEqual(["Isolde", "alias", "marr"]);
    s = s.update({ changes: chooseChange(s, s.doc.line(4).from, "isolde", "Isolde", ["Isolde Marr", "Isolde Senn"]) }).state;
    expect(s.doc.toString()).toBe("Varren waited.\n\n%% Isolde: Isolde Marr, Isolde Senn\nIsolde came to the quay.");
    s = s.update({ changes: chooseChange(s, s.doc.line(4).from, "isolde", "Isolde", null) }).state;
    expect(s.doc.toString()).toBe("Varren waited.\n\n%% Isolde: ?\nIsolde came to the quay.");
    expect(coloured(s).at(-1)![1]).toBe("ambiguous");
  });

  it("a choice line that singles out nobody is kept, with no ids, and changes nothing", () => {
    const s = stateOf("%% Isolde: Mar\nIsolde.");
    expect(choiceOn(s, 0)).toMatchObject({ ids: [], owners: ["marr", "senn"] });
    expect(coloured(s)[0]![1]).toBe("ambiguous");
  });
});

describe("the shared name's card and strip", () => {
  const labels = (el: HTMLElement) => [...el.querySelectorAll('[data-testid="shared-strip"] button')].map((b) => b.textContent);

  it("an ambiguous name lists every claimant with their one-liner, then From here: Marr · Senn · Both", () => {
    const chosen: (string[] | null)[] = [];
    const dom = sharedCardDom("Isolde", [marr, senn], { choose: (ids) => chosen.push(ids), open: () => {} });
    expect(dom.textContent).toContain("Isolde Marr · Keeps the lamp at Old Harbour.");
    expect(dom.textContent).toContain("Isolde Senn · A ferry pilot.");
    expect(labels(dom)).toEqual(["Marr", "Senn", "Both"]);
    (dom.querySelectorAll('[data-testid="shared-strip"] button')[2] as HTMLButtonElement).click();
    expect(chosen).toEqual([["marr", "senn"]]);
  });

  it("a settled one offers the others, Both and Unsure; with three claimants, All", () => {
    const box = document.createElement("div");
    expect(labels(settledRow(box, [marr, senn], ["marr"], { choose: () => {}, open: () => {} }))).toEqual(["Senn", "Both", "Unsure"]);
    expect(labels(settledRow(document.createElement("div"), [marr, senn], ["marr", "senn"], { choose: () => {}, open: () => {} }))).toEqual(["Marr", "Senn", "Unsure"]);
    const third = card("lowe", "Isolde Lowe");
    expect(labels(sharedCardDom("Isolde", [marr, senn, third], { choose: () => {}, open: () => {} }))).toEqual(["Marr", "Senn", "Lowe", "All"]);
  });

  it("a choice line that singles out nobody offers the claimants to put in", () => {
    const put: string[] = [];
    const dom = badChoiceStripDom("Isolde", [marr, senn], (id) => put.push(id));
    expect([...dom.querySelectorAll("button")].map((b) => b.textContent)).toEqual(["Isolde Marr", "Isolde Senn"]);
  });

  it("tells claimants apart by the word only they have", () => {
    expect(shortNames(["Isolde Marr", "Isolde Senn"])).toEqual(["Marr", "Senn"]);
    expect(shortNames(["Varren Hale", "Ilse Brand"])).toEqual(["Varren", "Ilse"]);
    expect(shortNames(["Linnet", "Linnet Dray"])).toEqual(["Linnet", "Dray"]);
  });
});

describe("what counts", () => {
  const chapter = (id: string, body: string): ThreadChapter => ({ id, title: id, body, state: "current", project: "p", project_name: "P" });

  it("the thread leaves out unsettled paragraphs and says so", () => {
    const r = thread([chapter("one", "Isolde came.\nIsolde Marr left.\n%% Isolde: Marr\nIsolde wept."), chapter("two", "Isolde waited.")], matcher, ["marr"], "paragraphs");
    expect(r.paragraphs).toBe(2);
    expect(r.unsettled).toEqual({ paragraphs: 2, form: "Isolde" });
    expect(unsettledLine(r.unsettled)).toBe("+ 2 paragraphs where “Isolde” isn’t settled");
    // Both counts for each
    const both = thread([chapter("one", "%% Isolde: Marr, Senn\nIsolde sang.")], matcher, ["senn"], "paragraphs");
    expect([both.paragraphs, both.unsettled]).toEqual([1, null]);
  });

  it("the planning reading too", () => {
    const r = planningReading({
      entries: [{ id: "j", entry_date: "2026-01-02", title: "Notes", body: "Isolde knows.\n%% Isolde: Senn\nIsolde knew.", project: null } as never],
      items: [], decisions: [], matcher, ids: ["senn"], mode: "paragraphs", kinds: new Set(["journal"]),
    });
    expect(r.counts.paragraphs).toBe(1);
    expect(r.counts.unsettled).toEqual({ paragraphs: 1, form: "Isolde" });
  });

  it("the cast lists an unsettled name once, with its claimants", () => {
    const m = (entity_id: string, entity_name: string, start: number, kind: Mention["kind"], matched_text = "Isolde"): Mention =>
      ({ entity_id, entity_name, entity_kind: "character", start, end: start + matched_text.length, matched_text, kind });
    const cast = castOf([
      m("marr", "Isolde Marr", 0, "ambiguous"), m("senn", "Isolde Senn", 0, "ambiguous"),
      m("senn", "Isolde Senn", 20, "ambiguous", "Isolde's"), m("marr", "Isolde Marr", 20, "ambiguous", "Isolde's"),
      m("marr", "Isolde Marr", 40, "alias"), m("varren", "Varren Hale", 50, "exact", "Varren Hale"),
    ]);
    expect(cast.named.map((n) => [n.name, n.count])).toEqual([["Isolde Marr", 1], ["Varren Hale", 1]]);
    expect(cast.unsettled).toEqual([{ form: "Isolde", claimants: [{ id: "marr", name: "Isolde Marr", kind: "character" }, { id: "senn", name: "Isolde Senn", kind: "character" }], short: ["Marr", "Senn"], count: 2 }]);
  });

  it("the mentions strip draws unsettled-only chapters faintly and adds a line", () => {
    const ch = (id: string, index: number): StoryChapter => ({ id, title: id, project: "p", project_name: "P", position: index, index } as StoryChapter);
    const s = mentionStrip([ch("a", 0), ch("b", 1), ch("c", 2)], new Map([["a", 2]]), "marr", null, undefined, new Map([["b", 4], ["c", 2], ["a", 1]]));
    expect(s.rows[0]!.cells.map((c) => [c.count, c.unsettled])).toEqual([[2, 1], [0, 4], [0, 2]]);
    expect(s.line).toContain("+ 7 unsettled in 3 chapters");
  });

  it("the companion: no connection or Continuity from an ambiguous name, a settled one counts", () => {
    const run = (text: string) => analyse({
      text, matcher, card: (id) => byId.get(id), linked: new Set(), presence: [], resolved: new Set(), longSentence: 0,
    });
    const pairs = (text: string) => run(text).filter((f) => f.rule === "unrecorded").map((f) => f.key);
    expect(pairs("Isolde met Varren Hale.")).toEqual([]);
    expect(pairs("%% Isolde: Senn\nIsolde met Varren Hale.")).toEqual([linkKey("senn", "varren")]);
    // not a new name either, and the choice line is no loose end
    const fs = run("%% Isolde: Senn\nIsolde met Isolde again. Isolde.");
    expect(fs.some((f) => f.rule === "new_name" || f.rule === "margin")).toBe(false);
  });
});
