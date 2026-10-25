// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { BOOK, tid } from "./common";

const steps: Step[] = [
  {
    go: BOOK,
    target: { css: tid("chapter-when") },
    say: "Every chapter can say when it is set. The Ferryman's Daughter happens in year 412, and Ash Season a year later.",
  },
  {
    target: { css: `${tid("chapters")} a`, text: "What the River Kept" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "twenty years" },
    say: "Chapter 3 mentions something that happened long before the book. Let's put it in the world's history.",
  },
  {
    target: { css: `${tid("editor")} .cm-line`, text: "twenty years" },
    act: { selectText: "We argued about it for twenty years" },
    wait: { css: tid("passage-strip") },
    say: "Select the passage that tells it. A quiet strip under the selection offers what can be done with it.",
  },
  {
    target: { css: `${tid("passage-strip")} button`, text: "Record as event" },
    act: { click: true },
    wait: { css: tid("record-form") },
    say: "Record as event turns the passage into history, and keeps the passage as the way the book tells it.",
  },
  {
    target: { css: `${tid("record-form")} input[aria-label="Event"]` },
    act: { fill: "The compass argument begins" },
    say: "Name the event. The people named in the passage are ticked as taking part.",
  },
  {
    target: { css: `${tid("record-form")} input[aria-label="When"]` },
    act: { fill: "392" },
    say: "Twenty years before the book: year 392. Left empty, it would wait in the Timeline's unplaced tray.",
  },
  {
    target: { css: `${tid("record-form")} input[aria-label="When"]` },
    act: { key: "Enter" },
    wait: { css: tid("toast"), text: "Recorded" },
    say: "Enter records it.",
    read: 1200,
  },
  {
    target: { css: `${tid("toast")} button`, text: "Open" },
    act: { click: true },
    wait: { css: tid("told-in") },
    say: "The note at the bottom offers to open what was just made.",
  },
  {
    target: { css: tid("told-in") },
    say: "The event's page knows where the book tells it, so the passage is never lost.",
  },
  {
    go: "/w/{w}/timeline",
    target: { css: tid("era-band") },
    say: "The Timeline draws the world in the order things happened. Eras are bands: the Lock Years, with the Ash Summers inside them.",
  },
  {
    target: { css: tid("fold") },
    say: "Long empty stretches fold up, so a few centuries don't swallow the page. Scroll on the page to zoom in.",
  },
  {
    target: { css: tid("era-filter") },
    act: { choose: "The Lock Years" },
    wait: { css: `${tid("timeline")} [data-testid="mark"]`, text: "compass argument" },
    say: "Choosing an era shows only its years, so events close together open out.",
  },
  {
    target: { css: `${tid("timeline")} [data-testid="mark"]`, text: "compass argument" },
    say: "The new event sits in year 392, two years after the Spring Flood.",
  },
  {
    target: { css: tid("book-band") },
    say: "The books sit where their chapters are set: The Ferryman's Daughter in 412.",
  },
  {
    target: { css: tid("era-filter") },
    act: { choose: "The Ash Summers" },
    wait: { css: '[data-testid="mark"][data-label="The Mountain Fires"]' },
    say: "The Ash Summers are the years the mountains kept burning, 410 to 414.",
  },
  {
    target: { css: '[data-testid="mark"][data-label="The Mountain Fires"]' },
    act: { hover: true },
    wait: { css: tid("cause-arrow") },
    say: "Rest on an event to see what caused it and what it caused.",
  },
  {
    target: { css: tid("cause-arrow") },
    say: "The Mountain Fires are recorded as causing the Flood of Lanterns, which came a year before them. The arrow says so, and Checks flags it.",
  },
  {
    target: { css: tid("era-filter") },
    act: { choose: "" },
    say: "Back to every era.",
    read: 900,
  },
  {
    target: { css: tid("tab-told") },
    act: { click: true },
    wait: { css: tid("told-row") },
    say: "Told lists the same events in book order.",
  },
  {
    target: { css: tid("told-row"), text: "Ferryman's Tale" },
    say: "A dot to the left of the line is a step back in time: the Ferryman's Tale is set forty years before the rest.",
  },
  {
    target: { css: tid("tab-history") },
    act: { click: true },
    say: "History leaves the books out and keeps only what came before them.",
  },
  {
    go: "/w/{w}/checks",
    target: { css: tid("check"), text: "Oskar" },
    say: "Checks reads the same clock: Oskar is named in Ash Season after his recorded death. Naming him in the tale, set earlier, is fine.",
  },
];

export const timeline: Tour = {
  id: "timeline",
  title: "Story time and the Timeline",
  blurb: "When chapters are set, recording an event from a passage, and reading the Timeline.",
  minutes: 4,
  covers: ["When a chapter is set", "Record as event", "Timeline", "Checks"],
  steps,
};
