// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { tid } from "./common";

const ED = tid("editor");

const steps: Step[] = [
  {
    go: "/w/{w}/journal?tab=loose",
    target: { css: `${tid("journal-loose")} a`, text: "Hesper's age" },
    say: "The Journal is thinking on paper, dated. Loose ends gathers every ?? and TK in it, oldest first: Hesper's age has been an open question since 2021.",
  },
  {
    target: { css: 'nav.tabs [role="tab"]', text: "Entries" },
    act: { click: true },
    wait: { css: tid("since-count") },
    say: "Entries lists them newest first, back to 2014. The dimmed count on an entry is how many decisions and changes since it was written touch the names in it.",
  },
  {
    target: { css: `${tid("journal-entry")} .journal-link`, text: "What the Wardens want" },
    act: { click: true },
    wait: { css: `${ED} .cm-k-character`, text: "Ilse Marrow" },
    say: "Open What the Wardens want, from 2019. An entry opens in the same editor as a chapter, with the names coloured and the world's cards.",
  },
  {
    target: { css: `${ED} .cm-k-faction`, text: "River Wardens" },
    act: { selectText: "River Wardens", exact: true },
    wait: { css: tid("name-card"), text: "planned" },
    say: "Select a name for its card. In the Journal the card shows planned facts too, marked: the Wardens' age, three hundred years, was planned in this entry.",
  },
  {
    target: { css: `${ED} .cm-k-character`, text: "Ilse Marrow" },
    act: { selectText: "Ilse Marrow knows the toll is older than the locks", exact: true },
    wait: { css: tid("selection-strip") },
    say: "Now something new. Select what Ilse Marrow knows, and a strip offers what can be made of it.",
  },
  {
    target: { css: `${tid("selection-strip")} button`, text: "Record a fact" },
    act: { click: true },
    wait: { css: tid("fact-form") },
    say: "Record a fact. From the Journal it starts as planned, and remembers this entry and the passage.",
  },
  {
    target: { css: `${tid("fact-form")} input[aria-label="Label"]` },
    act: { fill: "knows" },
    say: "Ilse Marrow is chosen already, as the name in the passage. A label…",
  },
  {
    target: { css: `${tid("fact-form")} input[aria-label="Value"]` },
    act: { fill: "the toll is older than the locks" },
    say: "…and a value.",
    read: 900,
  },
  {
    target: { css: `${tid("fact-form")} input[aria-label="Value"]` },
    act: { key: "Enter" },
    wait: { css: tid("toast"), text: "Recorded" },
    say: "Enter records it on her page as planned, until the book says so.",
  },
  {
    target: { css: `${ED} .cm-line`, text: "first toll was paid" },
    act: { selectText: "That is why the Flood of Lanterns frightens them." },
    wait: { css: tid("passage-strip") },
    say: "A passage can become a spark or a question too. Select the paragraph about the first toll, paid in lanterns.",
  },
  {
    target: { css: `${tid("passage-strip")} button`, text: "Question" },
    act: { click: true },
    wait: { css: tid("item-form") },
    say: "Question. The names in the passage are ticked, so it is tagged with them: the Outer Sound, the Flood of Lanterns.",
  },
  {
    target: { css: `${tid("item-form")} button`, text: "Save" },
    act: { click: true },
    wait: { css: tid("toast"), text: "Question saved" },
    say: "Save. It waits in the inbox, linked back to this passage, and the entry's Loose ends tab lists it.",
  },
  {
    go: "/w/{w}/bible/k/character",
    target: { css: `${tid("bible-list")} a.kname`, text: "Hesper Quill" },
    act: { click: true },
    wait: { css: `${tid("facts")} ${tid("planned-in")}` },
    say: "Plans become canon. Hesper Quill was thought up in the Journal long before she reached the book.",
  },
  {
    target: { css: `${tid("facts")} ${tid("planned-in")}` },
    say: "Her trade was planned in The first map, in 2014, and made canon in The Cartographer. The fact keeps both: the passage in the book, and where it was first planned.",
  },
  {
    target: { css: tid("read-planning-link") },
    act: { click: true },
    wait: { css: tid("planning-year") },
    say: "… in the planning reads everything that names her in the Journal, the inbox and the decisions, oldest first.",
  },
  {
    target: { css: tid("planning-entry"), text: "The first map" },
    say: "2014 comes first, with the years between marked. She began as a mapmaker from Greywater whose maps go out of date.",
  },
  {
    go: "/w/{w}/checks",
    target: { css: tid("include-planned") },
    act: { click: true },
    wait: { css: tid("check"), text: "planned dead" },
    say: "Checks leaves planned facts out, since they aren't in the book yet. Include planned counts them as if they were.",
  },
  {
    target: { css: tid("check"), text: "planned dead" },
    say: "Brother Cade's death is only planned, after chapter 3, so it is a finding only now: Ash Season still names him. Tagged planned, it is something to settle, not a mistake.",
  },
];

export const journal: Tour = {
  id: "journal",
  title: "Planning in the Journal",
  blurb: "Journal entries with the world tools, planned facts, questions from a passage, the planning reading, and Include planned.",
  minutes: 5,
  covers: ["Journal", "Planned facts", "Sparks and questions", "Planning reading", "Include planned"],
  steps,
};
