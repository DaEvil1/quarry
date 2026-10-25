// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { tid } from "./common";

const steps: Step[] = [
  {
    go: "/w/{w}",
    target: { css: tid("premise") },
    say: "A world's front page is for getting back in after weeks away. At the top, the premise in a line: a ferry-girl, a delta of nine channels, and the Wardens who would lock them.",
  },
  {
    target: { css: tid("left-off") },
    say: "Where you left off: the latest note you wrote for next time, and where you were when you wrote it.",
  },
  {
    target: { css: `${tid("left-off")} button`, text: "more" },
    act: { click: true },
    // the chapter's note, whichever comes first (the demo also has one in the Journal's “Loose threads”)
    wait: { css: `${tid("left-off")} a[href*="/chapters/"]` },
    say: "There is more than one. A note can be left in any chapter or journal entry.",
  },
  {
    target: { css: tid("lately") },
    say: "Lately sums up the last days: words written in each book, entries added or changed, items captured, decisions made.",
  },
  {
    target: { css: tid("latest-decisions") },
    say: "The latest decisions, so what was settled stays settled: Oskar dies in chapter 2, and the compass points home, never north.",
  },
  {
    target: { css: tid("open-questions") },
    say: "Questions still open, such as whether Pell knows who Rook is afraid of. The ?? count is the places in the Journal marked as unsure.",
  },
  {
    target: { css: `${tid("left-off")} a[href*="/chapters/"]` },
    act: { click: true },
    wait: { css: tid("back-in") },
    say: "Continue opens the chapter at the place you stopped: chapter 3, “What the River Kept”.",
  },
  {
    target: { css: tid("back-in") },
    say: "The panel repeats the last words before the cursor, and the note: Tamsin opens the compass in front of Brother Cade. Go there jumps back if you have wandered off.",
  },
  {
    target: { css: `${tid("editor")} .cm-content` },
    act: { cursorAt: 'good argument."' },
    say: "So write it. Put the cursor at the end of the chapter.",
    read: 1600,
  },
  {
    target: { css: `${tid("editor")} .cm-content` },
    act: {
      type: "\n\nTamsin opened the compass on the table between them. The needle swung past the lamp, past Brother Cade, past the door, and settled on the dark window: on the flats, on the water that had kept her father.",
    },
    wait: { css: `${tid("editor")} .cm-line`, text: "kept her father" },
    say: "A paragraph of the scene the note asked for.",
    read: 1200,
  },
  {
    // also gives the word count its moment to catch up, so leaving next counts the new words
    target: { css: tid("word-count") },
    say: "It saves as you go, and the word count keeps up when you pause.",
  },
  {
    go: "/w/{w}",
    target: { css: tid("leave-note") },
    say: "Leaving a chapter you wrote in, Quarry asks once what comes next. Skip is always there.",
  },
  {
    target: { css: "#leave-note" },
    act: { fill: "Cade explains what the compass really points at" },
    say: "A line is enough.",
    read: 900,
  },
  {
    target: { css: `${tid("leave-note")} button`, text: "Save and go" },
    act: { click: true },
    wait: { css: tid("left-off"), text: "really points at" },
    say: "Save and go. Next time, the front page offers this note first.",
  },
  {
    target: { css: `${tid("focus-switch")} button`, text: "Planning" },
    act: { click: true },
    wait: { css: `${tid("focus-switch")} button[aria-pressed="true"]`, text: "Planning" },
    say: "Writing or Planning says what is up front in this world, and it can change any time. In a stretch of planning, choose Planning.",
  },
  {
    target: { css: `.nav ${tid("nav-journal")}` },
    say: "The nav reorders at once: the Journal and the inbox lead, the Timeline joins them, and the books come last. Nothing is hidden either way.",
  },
  {
    target: { css: `${tid("focus-switch")} button`, text: "Writing" },
    act: { click: true },
    wait: { css: `${tid("focus-switch")} button[aria-pressed="true"]`, text: "Writing" },
    say: "Writing puts the books first again, and the world opens where you last were. Under Planning it opens on this front page.",
  },
];

export const backIn: Tour = {
  id: "back-in",
  title: "Getting back in",
  blurb: "The world's front page, continuing where you stopped, the note for next time, and the Writing or Planning focus.",
  minutes: 2,
  covers: ["Front page", "Where you left off", "A note for next time", "Focus"],
  steps,
};
