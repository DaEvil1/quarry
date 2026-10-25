// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { BOOK, tid } from "./common";

const steps: Step[] = [
  {
    go: "/w/{w}/p/ash-season",
    target: { css: tid("experiment-row") },
    say: "An experiment is another draft of one or more chapters. The book doesn't change while you try it. Ash Season has one across its first two chapters.",
  },
  {
    target: { css: `${tid("experiment-row")} button` },
    act: { click: true },
    wait: { css: tid("experiment") },
    say: "Open it.",
    read: 1200,
  },
  {
    target: { css: tid("drafts") },
    say: "Each draft is a chapter of its own, written in the same editor. These two began as copies of the chapters they would replace.",
  },
  {
    target: { css: tid("read-as-if") },
    act: { click: true },
    wait: { css: tid("read-as-if-line") },
    say: "Read as if accepted: the whole book with the drafts in place, to judge it as a reader would.",
  },
  {
    target: { css: tid("read-as-if-line") },
    say: "The line at the top says which experiment you are reading.",
  },
  {
    go: BOOK,
    target: { css: '[aria-label="Pick chapter 3"]' },
    act: { click: true },
    wait: { css: tid("selection-bar") },
    say: "Now one of your own. In The Ferryman's Daughter, pick chapter 3…",
  },
  {
    target: { css: '[aria-label="Pick chapter 4"]' },
    act: { click: true, shift: true },
    wait: { css: tid("selection-bar"), text: "Chapters 3–4" },
    say: "…and shift-click chapter 4 to take both.",
  },
  {
    target: { css: tid("start-experiment") },
    act: { click: true },
    wait: { css: tid("start-form") },
    say: "Start an experiment over them.",
    read: 1200,
  },
  {
    target: { css: "#exp-title" },
    act: { fill: "Cade tells it" },
    say: "Give it a working title. Starting from copies means revising rather than a blank page.",
  },
  {
    target: { css: `${tid("start-form")} button[type="submit"]` },
    act: { click: true },
    wait: { css: tid("experiment"), text: "Cade tells it" },
    say: "Start.",
    read: 900,
  },
  {
    target: { css: tid("drafts") },
    say: "Two drafts, copied from chapters 3 and 4. Rewrite them as much as you like; the book stays as it was.",
  },
  {
    target: { css: `${tid("experiment")} ${tid("accept")}` },
    act: { click: true },
    wait: { css: tid("retire-review") },
    say: "Happy with it? Accept puts the drafts in the book. First, a short review.",
  },
  {
    target: { css: tid("retire-review") },
    say: "What is tied to the chapters being retired is listed here: facts, relationships, where people are. Keep, move or drop each one. Nothing goes quietly.",
  },
  {
    target: { css: `${tid("retire-review")} input[placeholder="a harvest note"]` },
    act: { fill: "Tamsin alone with the compass in the guest room" },
    say: "One line per chapter on what was alive in it, for Salvage. Optional.",
  },
  {
    target: { css: tid("review-confirm") },
    act: { click: true },
    wait: { css: ".toast", text: "Accepted" },
    say: "Confirm.",
    read: 900,
  },
  {
    target: { css: ".toast", text: "Accepted" },
    say: "The drafts are chapters 3 and 4 now. Changed your mind? Undo puts it all back, the review too.",
  },
  {
    go: `${BOOK}/salvage`,
    target: { css: tid("salvage-entry"), text: "What the River Kept" },
    say: "The old chapters wait in Salvage with their harvest notes. They can be searched, and copied into a later experiment.",
  },
];

export const experiments: Tour = {
  id: "experiments",
  title: "Restructuring with experiments",
  blurb: "Trying other drafts of a range of chapters, reading them in place, accepting, and Salvage.",
  minutes: 2,
  covers: ["Experiments", "Read as if accepted", "The review", "Salvage"],
  steps,
};
