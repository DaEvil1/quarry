// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { BOOK, tid } from "./common";

const text = { css: `${tid("editor")} .cm-content` };

const steps: Step[] = [
  {
    go: BOOK,
    target: { css: `${tid("chapters")} a`, text: "Lanterns on the Water" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "came early that year" },
    say: "Chapter 2 of The Ferryman's Daughter, the night of the Flood of Lanterns. A few slips are planted in it.",
  },
  {
    target: { css: `${tid("editor")} .cm-name`, text: "Tamsin" },
    say: "Names from the bible are coloured by kind as you write: Tamsin as a character, Carrow Ferry as a place. Rest the pointer on one for its card.",
  },
  {
    target: { css: tid("tab-proofreader") },
    act: { click: true },
    wait: { css: tid("findings-proofreader") },
    say: "Beside the text, the companion: five tabs, each a reader with its own rules. The Proofreader has found a doubled “the the”, and “Oscar” where the bible says Oskar.",
  },
  {
    target: text,
    act: { cursorAt: "the the", before: true },
    say: "Findings can be fixed from the keyboard. Put the cursor on “the the”…",
    read: 1800,
  },
  {
    target: text,
    act: { key: "Enter", alt: true },
    wait: { css: tid("finding-strip") },
    say: "…and press Alt+Enter: its quick fixes open right there.",
    read: 1600,
  },
  {
    target: { css: `${tid("finding-strip")} button`, text: "Remove the second" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "flats, the slow bell" },
    say: "Remove the second “the”.",
    read: 1000,
  },
  {
    target: text,
    act: { key: "F8" },
    wait: { css: tid("near-miss-strip") },
    say: "F8 goes to the next likely misspelling and opens its strip. The next one here is “Oscar” again.",
  },
  {
    target: { css: `${tid("near-miss-strip")} button`, text: "Replace with" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "Oskar Vey said" },
    say: "Replace puts in the bible's name. Another spelling would keep Oscar as a name for him; Not a typo stops the flag.",
  },
  {
    target: { css: tid("tab-continuity") },
    act: { click: true },
    wait: { css: tid("findings-continuity"), text: "Mountain Fires" },
    say: "Continuity holds the chapter against what is recorded. The Mountain Fires are recorded as causing the Flood of Lanterns, which comes a year before them.",
  },
  {
    go: BOOK,
    target: { css: `${tid("chapters")} a`, text: "What the River Kept" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-margin` },
    say: "On to chapter 3. Its dimmed line near the top starts with %%: a margin note to yourself, kept out of the word count.",
  },
  {
    target: { css: tid("tab-connections") },
    act: { click: true },
    wait: { css: tid("findings-connections"), text: "Pell and Brother Cade" },
    say: "Connections notices names that share a sentence with nothing recorded between them, like Pell and Brother Cade. Record how… adds the relationship from here.",
  },
  {
    target: { css: tid("tab-archivist") },
    act: { click: true },
    wait: { css: tid("findings-archivist"), text: "Rook" },
    say: "The Archivist keeps the bible in step with the text. “Rook” appears twice and isn't in the bible yet.",
  },
  {
    target: { css: `${tid("findings-archivist")} .finding[data-rule="new_name"] button`, text: "Character" },
    act: { click: true },
    wait: { css: tid("findings-archivist"), text: "Rook has no one-line summary" },
    say: "One click makes Rook a character in this book's bible. The Archivist then asks for a one-line summary.",
  },
  {
    target: { css: tid("tab-looseEnds") },
    act: { click: true },
    wait: { css: "#next-note" },
    say: "Loose ends gathers what is left open here: the margin note, a question made from a passage, a thought stashed last time, and your note for next time.",
  },
  {
    target: text,
    act: { key: "s", ctrl: true, shift: true },
    wait: { css: "#stash-thought" },
    say: "A thought that would break the sentence? Ctrl+Shift+S stashes it without leaving the text.",
  },
  {
    target: { css: "#stash-thought" },
    act: { fill: "Does Rook owe Oskar money?" },
    say: "Write it in a line.",
    read: 900,
  },
  {
    target: { css: ".checkpoint-bar button", text: "Stash" },
    act: { click: true },
    wait: { css: tid("loose-item"), text: "Rook owe" },
    say: "It goes to the inbox to be sorted later, tied to this chapter, and shows here in Loose ends.",
  },
  {
    target: { css: tid("mode") },
    say: "Drafting keeps new findings for a natural break, such as a line of *** or opening a tab. Revising marks them in the text as they are found.",
  },
];

export const companion: Tour = {
  id: "companion",
  title: "Writing a chapter with the companion",
  blurb: "Names coloured as you write, the companion's five tabs, fixes from the keyboard, and stashing a thought.",
  minutes: 2,
  covers: ["Names by kind", "The five tabs", "Alt+Enter and F8", "Margin notes", "Stash a thought"],
  steps,
};
