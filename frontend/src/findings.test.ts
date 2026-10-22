import { describe, expect, it } from "vitest";

import { analyse, linkKey, storyText, type AnalyseInput, type Finding } from "./world/findings";
import type { Card } from "./world/cards";
import { Matcher } from "./world/matcher";

const card = (id: string, name: string, kind: Card["kind"] = "character", summary = ""): Card => ({
  id,
  name,
  kind,
  aliases: [],
  first_name: null,
  match_case: true,
  exclusions: [],
  summary,
  facts: [],
  relations: [],
});
const cards = [card("v", "Varren"), card("i", "Isolde", "character", "Keeper's daughter"), card("h", "Old Harbour", "place"), card("l", "Lamphouse", "place")];
const byId = new Map(cards.map((c) => [c.id, c]));

function run(text: string, extra: Partial<AnalyseInput> = {}): Finding[] {
  return analyse({
    text,
    matcher: new Matcher(cards),
    card: (id) => byId.get(id),
    linked: new Set(),
    presence: [],
    resolved: new Set(),
    longSentence: 0,
    ...extra,
  });
}
const rules = (fs: Finding[], editor: string) => fs.filter((f) => f.editor === editor).map((f) => [f.rule, f.message]);

describe("the companion's text findings", () => {
  it("done when: two unconnected characters and a new name, each one click away", () => {
    const fs = run("Varren met Isolde on the pier. Brannoch watched them.\n\nLater, Varren asked Brannoch to leave.");
    const conn = fs.filter((f) => f.rule === "unrecorded");
    expect(conn[0]).toMatchObject({ strength: "strong", message: "Varren and Isolde share a sentence here.", a: { name: "Varren" }, b: { name: "Isolde" } });
    const name = fs.find((f) => f.rule === "new_name");
    expect(name).toMatchObject({ word: "Brannoch", message: "“Brannoch” appears 2× and isn't in the bible." });
    // once recorded, or said not to be connected, the pair is gone
    expect(run("Varren met Isolde.", { linked: new Set([linkKey("v", "i")]) }).some((f) => f.rule === "unrecorded")).toBe(false);
    expect(run("Varren met Isolde.", { resolved: new Set([`unrecorded|${linkKey("v", "i")}`]) }).some((f) => f.rule === "unrecorded")).toBe(false);
  });

  it("connection strength: sentence, paragraph, chapter", () => {
    const fs = run("Varren slept.\nIsolde woke. Old Harbour was quiet, and Isolde left Old Harbour.\n\nLamphouse.");
    const s = Object.fromEntries(fs.filter((f) => f.rule === "unrecorded").map((f) => [`${f.a!.name}+${f.b!.name}`, f.strength]));
    expect(s["Isolde+Old Harbour"]).toBe("strong");
    expect(s["Varren+Isolde"] ?? s["Isolde+Varren"]).toBe("weak");
  });

  it("a word only ever at the start of sentences is not a name; a known one never is", () => {
    const fs = run("Rain fell. Rain again. Varren nodded. Monday came, and Monday went. She waited, she She.");
    expect(fs.filter((f) => f.rule === "new_name")).toEqual([]);
  });

  it("where are they: several places around a character, none recorded", () => {
    const text = "Varren left Old Harbour for the Lamphouse.";
    expect(rules(run(text), "connections")).toContainEqual(["where", "Where is Varren? 2 places are named around them, none recorded."]);
    expect(run(text, { presence: [{ entity_id: "v", place: { id: "h", name: "Old Harbour", kind: "place" }, note: null }] }).some((f) => f.rule === "where")).toBe(false);
  });

  it("proofreading: doubled words, spacing, echoes, misspelled names, long sentences", () => {
    const fs = run("The the tide came  in , slowly.It was a lantern, the lantern swung. Varen waited. He had had enough.");
    expect(rules(fs, "proofreader")).toEqual([
      ["doubled", "“The the”: the word twice."],
      ["spacing", "Two spaces."],
      ["spacing", "A space before punctuation."],
      ["spacing", "No space after punctuation."],
      ["echo", "“lantern” again, 2 words after the last one."],
      ["near_miss", "“Varen”: Varren?"],
    ]);
    const doubled = fs.find((f) => f.rule === "doubled")!;
    expect(doubled.fix).toMatchObject({ insert: "", label: "Remove the second “the”" });
    expect(run("One two three four five six.", { longSentence: 5 }).map((f) => f.message)).toEqual(["A sentence of 6 words."]);
  });

  it("margin notes are left out of the story but listed as loose ends, with TKs", () => {
    const text = "Varren waits.\n%% Varren Varren should be angrier\nThe TK tide.";
    expect(storyText(text)).toBe("Varren waits.\n" + " ".repeat("%% Varren Varren should be angrier".length) + "\nThe TK tide.");
    const fs = run(text);
    expect(fs.some((f) => f.rule === "doubled")).toBe(false);
    expect(rules(fs, "looseEnds")).toEqual([
      ["tk", "TK: The TK tide."],
      ["margin", "Varren Varren should be angrier"],
    ]);
  });

  it("the archivist: entries without a one-liner, spellings worth adding", () => {
    const fs = run("Varen spoke. Isolde listened to Varren. Varen again.");
    expect(rules(fs, "archivist")).toEqual([
      ["no_summary", "Varren has no one-line summary yet."],
      ["other_name", "“Varen” is written 2× here: another name for Varren?"],
    ]);
  });
});
