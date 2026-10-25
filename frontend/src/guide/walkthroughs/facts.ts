// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { BOOK, tid } from "./common";

const PASSAGE = "Tamsin Vey let the last one fade before she cast off, the way her father had taught her: you give the river time to hear you.";

const steps: Step[] = [
  {
    go: BOOK,
    target: { css: `${tid("chapters")} a`, text: "The Crossing" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "Tamsin Vey let the last one fade" },
    say: "Facts are what you want to keep straight about an entry. The quickest way to record one is from the sentence that says it. Open The Crossing.",
  },
  {
    target: { css: `${tid("editor")} .cm-line`, text: "Tamsin Vey let the last one fade" },
    act: { selectText: PASSAGE, exact: true },
    wait: { css: tid("passage-strip") },
    say: "Select the passage. It says something about Tamsin worth remembering.",
  },
  {
    target: { css: `${tid("passage-strip")} button`, text: "Record a fact" },
    act: { click: true },
    wait: { css: tid("fact-form") },
    say: "Record a fact. Tamsin is the one named in the passage, so she is already chosen.",
  },
  {
    target: { css: `${tid("fact-form")} input[aria-label="Label"]` },
    act: { fill: "habit" },
    say: "A label: any word you like. Labels used before are offered as you type.",
  },
  {
    target: { css: `${tid("fact-form")} input[aria-label="Value"]` },
    act: { fill: "lets the tidecall fade before casting off" },
    say: "And the value.",
    read: 900,
  },
  {
    target: { css: `${tid("fact-form")} input[aria-label="Value"]` },
    act: { key: "Enter" },
    wait: { css: tid("toast"), text: "Recorded" },
    say: "Enter records it, true from this chapter on, with the passage kept as its evidence.",
  },
  {
    target: { css: `${tid("toast")} button`, text: "Open" },
    act: { click: true },
    wait: { css: `${tid("facts")} tr`, text: "habit" },
    say: "Open her page.",
    read: 900,
  },
  {
    target: { css: `${tid("facts")} tr`, text: "habit" },
    say: "The new fact, with where it says so: the passage and The Crossing.",
  },
  {
    target: { css: `${tid("facts")} tr`, text: "novice at Saltreach Abbey" },
    say: "Facts can change over the story. She is a ferry hand until Lanterns on the Water, and a novice at Saltreach Abbey from What the River Kept.",
  },
  {
    target: { css: tid("as-of") },
    act: { choose: "@time" },
    wait: { css: tid("as-of-time") },
    say: "As of reads the page at one point in the story: a chapter, or a time.",
  },
  {
    target: { css: tid("as-of-time") },
    act: { fill: "411" },
    say: "The book begins in year 412. Try the year before.",
    read: 1200,
  },
  {
    target: { css: ".as-of-time button", text: "Set" },
    act: { click: true },
    wait: { css: `${tid("facts")} tr.off`, text: "novice" },
    say: "What isn't true yet is greyed: in 411 she is still a ferry hand.",
  },
  {
    target: { css: tid("relationship"), text: "Saltreach Abbey" },
    say: "Relationships follow the same clock. She lives at Carrow Ferry; living at the abbey comes later.",
  },
  {
    target: { css: tid("family-tree-link") },
    act: { click: true },
    wait: { css: tid("family-tree") },
    say: "Parents, children and marriages make a family tree.",
    read: 1200,
  },
  {
    target: { css: `${tid("family-person")}[data-name="Corin Dray"]` },
    say: "Three generations: Agathe, her children Oskar and Linnet, and theirs. Nobody recorded Corin as Tamsin's cousin; the tree works it out.",
  },
  {
    target: { css: `${tid("family-person")}[data-name="Wenna the Ferrywoman"]` },
    say: "Wenna the Ferrywoman is recorded only as an ancestor, centuries back. The dashed line stands for the generations nobody wrote down.",
  },
  {
    go: "/w/{w}/where",
    target: { css: `${tid("where-Tamsin Vey")} td[data-chapter="What the River Kept"]` },
    say: "Where everyone is: a row per character, a column per chapter. Tamsin is recorded at Saltreach Abbey here; click any cell to record where someone is.",
  },
];

export const facts: Tour = {
  id: "facts",
  title: "Facts and relationships from the prose",
  blurb: "Recording a fact from a passage, reading an entry as of a point in the story, the family tree, and where everyone is.",
  minutes: 4,
  covers: ["Record a fact", "Facts and relationships", "As of", "Family tree", "Where everyone is"],
  steps,
};
