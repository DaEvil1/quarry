// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { tid } from "./common";

const CHARACTERS = "/w/{w}/bible/k/character";

const steps: Step[] = [
  {
    go: "/w/{w}",
    target: { css: tid("nav-kind-character") },
    act: { click: true },
    wait: { css: `${tid("bible-list")} a.kname`, text: "Tamsin Vey" },
    say: "The bible is everything you keep track of, listed by kind in the nav: characters, places, factions, events and the rest.",
  },
  {
    target: { css: `${tid("bible-list")} a.kname`, text: "Tamsin Vey" },
    act: { click: true },
    wait: { css: tid("pronunciation") },
    say: "Each kind is a table with a one-line summary and the facts most entries share. Open Tamsin Vey.",
  },
  {
    target: { css: "h1.kname" },
    say: "Her page starts with her name, how to say it (TAM-zin VAY) and her other names. “Tam” in the text counts as her too.",
  },
  {
    target: { css: tid("mention-strip") },
    say: "The mentions strip has a cell for every chapter of both books, darker where she is named more often. A bar under a cell marks her point-of-view chapters.",
  },
  {
    target: { css: tid("first-appearance") },
    say: "Where she first appears in each book, and below it every chapter, journal entry and note that names her.",
  },
  // pictures (docs/SPEC.md §17.2): Marrow Locks' gallery
  {
    go: "/w/{w}/bible/k/place",
    target: { css: `${tid("bible-list")} a.kname`, text: "Marrow Locks" },
    act: { click: true },
    wait: { css: tid("main-picture") },
    say: "An entry can have pictures, like a wiki's. Open Marrow Locks.",
  },
  {
    target: { css: tid("main-picture") },
    say: "Its main picture sits at the top of its page, and in the corner of its card wherever its name is shown.",
  },
  {
    target: { css: `${tid("main-picture")} button` },
    act: { click: true },
    wait: { css: tid("picture-viewer") },
    say: "A click opens the full view.",
    read: 1200,
  },
  {
    target: { css: tid("viewer-next") },
    act: { click: true },
    wait: { css: tid("viewer-caption"), text: "The locks from above" },
    say: "‹ › (or the arrow keys, or a swipe on the phone) step through all of the entry's pictures. Open full size has the whole picture.",
  },
  {
    target: { css: tid("viewer-close") },
    act: { click: true },
    wait: { css: tid("gallery") },
    say: "Close it.",
    read: 800,
  },
  {
    target: { css: `${tid("gallery-item")}:nth-child(2) ${tid("gallery-more")}` },
    act: { click: true },
    wait: { css: tid("make-main") },
    say: "The gallery is under the notes. Each picture has a caption of its own here, and More… to change it.",
  },
  {
    target: { css: tid("make-main") },
    act: { click: true },
    wait: { css: tid("main-caption"), text: "The locks from above" },
    say: "Make main puts the plan at the top of the page instead.",
  },
  {
    target: { css: tid("gallery-add") },
    say: "Add pictures… takes files from the computer, or the camera or the gallery on a phone. A picture pasted into a chapter goes on a line of its own, drawn under the line.",
  },
  {
    go: `${CHARACTERS}?book=the-ferrymans-daughter`,
    target: { css: `${tid("section-else")} tr`, text: "Corin Dray" },
    say: "An entry can belong to one book. Corin Dray is only in Ash Season's own bible, so with The Ferryman's Daughter chosen he is listed under Elsewhere.",
  },
  {
    target: { css: `${tid("bible-list")} a.kname`, text: "Moss" },
    act: { click: true },
    wait: { css: "details.matching summary" },
    say: "Moss is Pell's dog. Moss is also a word.",
  },
  {
    target: { css: "details.matching summary" },
    act: { click: true },
    wait: { css: "details.matching .chip", text: "moss grew" },
    say: "Matching in the text says how a name is found. “moss grew” is a phrase where Moss isn't a name.",
  },
  {
    target: { css: `${tid("first-appearance")} a`, text: "The Crossing" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "Moss grew thick" },
    say: "See it in The Crossing, where Moss first appears.",
    read: 1400,
  },
  {
    target: { css: `${tid("editor")} .cm-line`, text: "Moss grew thick" },
    say: "“Moss grew thick on the pilings” is left plain. A sentence later Moss is barking, and that one is marked as the dog.",
  },
  {
    target: { css: tid("nav-names") },
    act: { click: true },
    wait: { css: tid("near-miss-group"), text: "Tamsen" },
    say: "The name check lists words that look like misspelled names from the bible.",
  },
  {
    target: { css: tid("near-miss-group"), text: "Tamsen" },
    say: "“Tamsen” in The Crossing is one letter off Tamsin, and “Oscar” is used twice for Oskar. Replace them all, keep one as another spelling, or mark it as not a typo.",
  },
  {
    go: CHARACTERS,
    target: { css: `${tid("bible-list")} a.kname`, text: "Pell" },
    act: { click: true },
    wait: { css: "h1.kname .inline-text" },
    say: "Names change while you write. Pell has no family name yet, so give him one.",
  },
  {
    target: { css: "h1.kname .inline-text" },
    act: { click: true },
    wait: { css: 'h1.kname input[aria-label="Name"]' },
    say: "Click the name to edit it.",
    read: 1000,
  },
  {
    target: { css: 'h1.kname input[aria-label="Name"]' },
    act: { fill: "Pell Rushby" },
    say: "Type the new name.",
    read: 800,
  },
  {
    target: { css: 'h1.kname input[aria-label="Name"]' },
    act: { key: "Enter" },
    wait: { css: tid("toast"), text: "Kept" },
    say: "Enter saves it. “Pell” is kept as another name, so the chapters that say it still point to him. The note can take it away, or replace it in the text.",
  },
  {
    go: "/w/{w}/bible/labels",
    target: { css: `${tid("labels-event")} details[data-label="type"] > summary` },
    act: { click: true },
    wait: { css: `${tid("labels-event")} ${tid("without")}` },
    say: "Labels lists the fact labels in use, per kind. Every event is expected to have a type, and The Mountain Fires doesn't yet.",
  },
  {
    target: { css: `${tid("labels-character")} details[data-label="languages"] > summary` },
    say: "A label can hold several values at once: Hesper Quill speaks Delta speech and the Greywater chart-cant, and neither replaces the other.",
  },
];

export const bible: Tour = {
  id: "bible",
  title: "The bible",
  blurb: "Entries and their pages, pictures, names that aren't names, the name check, renaming, and labels.",
  minutes: 2,
  covers: ["Entries", "Mentions strip", "Pictures", "Book-only entries", "Name check", "Labels"],
  steps,
};
