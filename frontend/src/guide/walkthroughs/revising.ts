// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { BOOK, tid } from "./common";

const text = { css: `${tid("editor")} .cm-content` };
const LABEL = "before the cuts";

const steps: Step[] = [
  {
    go: BOOK,
    target: { css: tid("chapter-1") },
    say: "On the book's page every chapter carries a one-line summary and a status pill; click either to change it. The stages are this book's own: raw, rewritten, polished.",
  },
  {
    target: { css: tid("word-history") },
    say: "Words shows what was written and cut each day, from the chapters' history. No goals and no streaks: a day off is just an empty day.",
  },
  {
    go: `${BOOK}/replace?find=Oscar&replace=Oskar`,
    target: { css: tid("replace-hit") },
    say: "Find and replace works across every chapter and experiment. “Oscar”, a slip for Oskar, is in chapter 2 twice; each hit is previewed, and any can be unticked.",
  },
  {
    target: { css: tid("replace-button") },
    act: { click: true },
    wait: { css: tid("replace-done") },
    say: "Replace. Each chapter it changes gets a checkpoint first.",
    read: 1600,
  },
  {
    target: { css: `${tid("replace-done")} button`, text: "Undo" },
    act: { click: true },
    wait: { css: tid("replace-undone") },
    say: "And Undo puts every chapter back as it was.",
    read: 1600,
  },
  {
    go: BOOK,
    target: { css: `${tid("chapters")} a`, text: "The Crossing" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "tidecall" },
    say: "Now one chapter, “The Crossing”, for a closer revision.",
  },
  {
    target: text,
    act: { key: "s", ctrl: true },
    wait: { css: "#checkpoint-label" },
    say: "Before changing much, press Ctrl+S for a checkpoint. It can carry a label.",
  },
  {
    target: { css: "#checkpoint-label" },
    act: { fill: LABEL },
    say: "Name it.",
    read: 800,
  },
  {
    target: { css: ".checkpoint-bar button", text: "Keep" },
    act: { click: true },
    wait: { css: ".notice", text: LABEL },
    say: "Keep it.",
    read: 800,
  },
  {
    target: { css: `${tid("mode")} button`, text: "Revising" },
    act: { click: true },
    wait: { css: `${tid("mode")} button[aria-pressed="true"]`, text: "Revising" },
    say: "Switch to Revising: findings are marked in the text, and the changes since a checkpoint can be shown.",
  },
  {
    target: { css: "#changes-since" },
    act: { choose: LABEL },
    wait: { css: tid("changes-line"), text: LABEL },
    say: "Show changes since “before the cuts”. From now on what changes is marked in the text and counted here.",
  },
  {
    target: { css: `${tid("editor")} .cm-line`, text: "read your calendar" },
    act: { selectText: "The river doesn't read your calendar" },
    wait: { css: tid("selection-strip") },
    say: "Select a line you're unsure of: Oskar's answer about the river and the calendar.",
  },
  {
    target: text,
    act: { key: "x", ctrl: true, shift: true },
    wait: { css: tid("chapter-cut"), text: "calendar" },
    say: "Ctrl+Shift+X cuts it to the bin. Where it was is marked as removed, and the panel lists it under Cut from this chapter.",
  },
  {
    go: `${BOOK}/salvage?tab=cuts`,
    // newest first: the cut just made
    target: { css: `${tid("cut")} button`, text: "Put back" },
    act: { click: true },
    wait: { css: `${tid("cut")} button`, text: "Open and put back" },
    say: "Every cut waits in Salvage › Cuts, newest first, beside the bell-buoy passage cut a week ago. Changed your mind? Put back.",
  },
  {
    target: { css: `${tid("cut")} button`, text: "Open and put back" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "read your calendar" },
    say: "It goes back into its chapter, at the place found by the text around it.",
  },
  {
    target: { css: `${tid("mode")} button`, text: "Drafting" },
    act: { click: true },
    wait: { css: `${tid("mode")} button[aria-pressed="true"]`, text: "Drafting" },
    say: "The chapter reads as it did at the checkpoint again. Back to Drafting for writing.",
  },
  {
    target: { css: `${tid("companion")} a.kname`, text: "The Brass Compass" },
    act: { click: true },
    wait: { css: tid("read-thread") },
    say: "One more way to revise is to follow a single thread. Open the Brass Compass from the names in this chapter.",
  },
  {
    target: { css: tid("read-thread") },
    act: { click: true },
    wait: { css: tid("thread-count") },
    say: "Read in story order gives every passage that names the compass, chapter by chapter, as a reader meets them.",
  },
];

export const revising: Tour = {
  id: "revising",
  title: "Revising",
  blurb: "Summaries and statuses, word history, find and replace, a checkpoint and the changes since, the cuts bin, and one entry's thread.",
  minutes: 2,
  covers: ["Summaries and statuses", "Find and replace", "Changes since a checkpoint", "Cuts bin", "Read a thread"],
  steps,
};
