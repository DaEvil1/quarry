// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.
// Planning a chapter (docs/SPEC.md §18.6): chapter 3 with its plan beside it.

import type { Step, Tour } from "../engine";
import { tid } from "./common";

const SIDE = tid("plan-side");
const PLAN = `${SIDE} ${tid("editor")}`;
const BOOK = "/w/{w}/p/the-ferrymans-daughter";

const steps: Step[] = [
  {
    go: BOOK,
    target: { css: `${tid("chapter-3")} ${tid("chapter-plans")}` },
    say: "A chapter can have a plan: a journal entry written first, then read beside the chapter while writing it. Chapter 3 has two.",
  },
  {
    target: { css: `${tid("chapter-3")} ${tid("chapter-plans")}` },
    act: { click: true },
    wait: { css: `${PLAN} .cm-line`, text: "Brother Cade is about sixty" },
    say: "Open it with its plan beside it.",
    read: 1000,
  },
  {
    target: { css: `${SIDE} .plan-tabs` },
    say: "Half each: the chapter on the left, the plan on the right. Its plans are tabs, newest first: the second plan was written after the first didn't hold.",
  },
  {
    target: { css: tid("plan-tab"), nth: 1 },
    act: { click: true },
    wait: { css: `${PLAN} .cm-line`, text: "Tamsin comes to Saltreach Abbey" },
    say: "The first plan, from 20 September.",
    read: 1200,
  },
  {
    target: { css: tid("plan-tab"), nth: 0 },
    act: { click: true },
    wait: { css: `${PLAN} .cm-line`, text: "he looks away" },
    say: "Back to the second.",
    read: 900,
  },
  {
    target: { css: `${PLAN} .cm-line`, text: "he looks away" },
    act: { cursorAt: "he looks away." },
    say: "The plan pane is the Journal's editor, so planning goes on while writing.",
  },
  {
    target: { css: `${PLAN} .cm-line`, text: "he looks away" },
    act: { type: " He keeps the lid shut." },
    wait: { css: tid("plan-save-status"), text: "Saved" },
    say: "Type a line in the plan: it saves as the journal entry does, with its own History.",
  },
  {
    target: { css: `${PLAN} .cm-content` },
    act: { key: "p", ctrl: true, shift: true },
    wait: { css: ".chapter-main .cm-focused" },
    say: "Ctrl+Shift+P moves the cursor to the chapter, and pressed again, back to the plan.",
  },
  {
    target: { css: `${PLAN} .cm-k-character`, text: "Brother Cade" },
    act: { selectText: "Brother Cade", exact: true },
    wait: { css: tid("name-card"), text: "planned" },
    say: "A card in the plan reads as of chapter 3, with planned facts marked: that he is about sixty was planned in this plan.",
  },
  {
    target: { css: `${PLAN} .cm-line`, text: "What does Cade want" },
    act: { selectText: "What does Cade want with the compass ??" },
    wait: { css: "[data-testid=passage-strip], [data-testid=selection-strip]" },
    say: "A question from a passage of the plan…",
    read: 1000,
  },
  {
    target: { css: "[data-testid=passage-strip] button, [data-testid=selection-strip] button", text: "Question" },
    act: { click: true },
    wait: { css: tid("item-chapters"), text: "chapter 3" },
    say: "…is ticked for the chapter beside it, so it shows in that chapter's Loose ends.",
  },
  {
    target: { css: `${tid("item-form")} button`, text: "Save" },
    act: { click: true },
    wait: { css: tid("toast"), text: "Question saved" },
    say: "Save it.",
    read: 800,
  },
  {
    target: { css: ".chapter-tools button", text: "Panel" },
    act: { click: true },
    wait: { css: tid("tab-looseEnds") },
    say: "While the plan is open the chapter's panel folds away. Panel brings it back.",
  },
  {
    target: { css: tid("tab-looseEnds") },
    act: { click: true },
    wait: { css: tid("loose-item"), text: "What does Cade want" },
    say: "There it is, in chapter 3's Loose ends.",
  },
  {
    target: { css: tid("plan-divider") },
    say: "Drag the divider to give either side more room; a double-click puts it back to half. It keeps its place on this device.",
  },
  {
    go: BOOK,
    target: { css: `${tid("plans-waiting")} ${tid("waiting-plan")}`, text: "After the Locks" },
    say: "A plan can come before its chapter. After the Locks waits here, under Plans with no chapter yet.",
  },
  {
    target: { css: `${tid("waiting-plan")} ${tid("start-chapter")}` },
    act: { click: true },
    wait: { css: tid("start-chapter-row") },
    say: "Start a chapter from it, at the end or after a chapter you pick.",
  },
  {
    target: { css: tid("start-confirm") },
    act: { click: true },
    wait: { css: `${PLAN} .cm-line`, text: "Linnet Sorrel is on the gate" },
    say: "An empty chapter 5, titled as the plan is, opens with the plan beside it. Undo on the note takes it away again while it is empty.",
  },
  {
    phone: BOOK,
    in: "phone",
    target: { css: `${tid("chapter-3")} a`, text: "What the River Kept" },
    act: { click: true },
    wait: { css: tid("plan-button") },
    say: "On the phone the same chapter has no room for two.",
  },
  {
    in: "phone",
    target: { css: tid("plan-button") },
    act: { click: true },
    wait: { css: `${PLAN} .cm-line`, text: "he looks away" },
    say: "Plan flips the screen to the plan…",
  },
  {
    in: "phone",
    target: { css: tid("flip-back") },
    act: { click: true },
    wait: { css: ".chapter-main .cm-line", text: "They never found Oskar" },
    say: "…and the chapter's tab flips back. Each keeps its place and its cursor.",
  },
  {
    phone: false,
    say: "That's a chapter's plan: written freely in the Journal, read beside the chapter, and never ticked off.",
  },
];

export const planning: Tour = {
  id: "planning",
  title: "Planning a chapter",
  blurb: "A chapter's plan beside it, its tabs, cards and questions from it, a plan before its chapter, and the phone.",
  minutes: 1,
  covers: ["Plans", "The split", "Start a chapter from a plan"],
  steps,
};
