// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { BOOK_TWO, tid } from "./common";

/** the paragraph whose "Linnet" nothing settles yet: the first "Linnet" in the chapter */
const FIRST = { css: `${tid("editor")} .cm-line`, text: "Linnet sent word" };

const steps: Step[] = [
  {
    go: BOOK_TWO,
    target: { css: `${tid("chapters")} a`, text: "The Cartographer" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-name[data-hit="ambiguous"]` },
    say: "The delta has two Linnets: Linnet Dray, Tamsin's aunt, and Linnet Sorrel, who keeps the gates at Marrow Locks. Open The Cartographer in Ash Season.",
  },
  {
    target: { css: `${tid("editor")} .cm-name[data-hit="ambiguous"]` },
    say: "Here the text just says “Linnet”. It is marked as a name, but as one that could be either of them, and it counts for neither.",
  },
  {
    target: FIRST,
    act: { selectText: "Linnet", exact: true },
    wait: { css: tid("shared-card") },
    say: "Select the name to see who it could be.",
    read: 1200,
  },
  {
    target: { css: tid("shared-card") },
    say: "Both entries, each with its one line. The buttons below settle which one is meant, from here on.",
  },
  {
    phone: "/w/{w}/p/ash-season",
    in: "phone",
    target: { css: `${tid("chapters")} a`, text: "The Cartographer" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "Linnet sent word" },
    say: "On the phone it works the same way.",
    read: 1200,
  },
  {
    in: "phone",
    target: FIRST,
    act: { selectText: "Linnet", exact: true },
    wait: { css: tid("shared-card") },
    say: "A long press selects the name, and the same choices show under it.",
  },
  {
    phone: false,
    target: FIRST,
    act: { selectText: "Linnet", exact: true },
    wait: { css: `${tid("shared-strip")} button`, text: "Sorrel" },
    say: "Back at the desk. Word from the locks would come from the lock-keeper.",
    read: 1400,
  },
  {
    target: { css: `${tid("shared-strip")} button`, text: "Sorrel" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-margin`, text: "Linnet: Linnet Sorrel", nth: 1 },
    say: "Sorrel writes a choice line above the paragraph. From there on, “Linnet” means her.",
  },
  {
    target: { css: `${tid("editor")} .cm-margin`, text: "Linnet: Linnet Dray" },
    say: "A choice line is a margin note, left out of the word count and the manuscript. Further down, this one hands the name to Linnet Dray.",
  },
  {
    target: { css: `${tid("editor")} .cm-margin`, text: "Linnet: ?" },
    say: "And a question mark leaves it open again: nobody knows which Linnet Hesper means.",
  },
  {
    target: { css: tid("cast-unsettled") },
    say: "The chapter's cast lists what is still open: “Linnet?”, with a link to each of them.",
  },
  {
    target: { css: `${tid("cast-unsettled")} a`, text: "Sorrel" },
    act: { click: true },
    wait: { css: tid("unsettled") },
    say: "Open Linnet Sorrel.",
    read: 900,
  },
  {
    target: { css: tid("unsettled") },
    say: "Under her mentions, Not settled lists the uses of the name that nothing has decided. They aren't counted for her, or for Linnet Dray.",
  },
  {
    target: { css: tid("strip-line") },
    say: "Her mentions strip counts only the settled uses, and adds the open ones at the end of its line.",
  },
  {
    go: "/w/{w}/bible/k/character",
    target: { css: tid("also-tag") },
    say: "An entry can be of more than one kind. The Ninefold Delta is a place, and in this story it also acts like a character.",
  },
  {
    target: { css: `${tid("bible-list")} a.kname`, text: "The Ninefold Delta" },
    act: { click: true },
    wait: { css: tid("entry-kinds"), text: "also a" },
    say: "So it is listed with the characters too, as one entry.",
    read: 1200,
  },
  {
    target: { css: tid("entry-kinds") },
    say: "Its page says both: a place, also a character. It can have a character's relationships and a place's, and Make main swaps them round.",
  },
  {
    target: { css: tid("also-a") },
    say: "Add another kind here at any time. The entry keeps its name, mentions and history.",
  },
];

export const names: Tour = {
  id: "names",
  title: "Names shared by two entries",
  blurb: "Two Linnets in one chapter, settling which is meant with choice lines, and an entry that is two kinds at once.",
  minutes: 4,
  covers: ["Shared names", "Choice lines", "Not settled", "Phone", "Entries of two kinds"],
  steps,
};
