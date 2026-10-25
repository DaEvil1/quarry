// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do. Export,
// Restore, passkeys and deleting a world are only pointed at: they download, pick files, talk to the device's
// authenticator or can't be taken back.

import type { Step, Tour } from "../engine";
import { BOOK, tid } from "./common";

const revisions = `${tid("history")} .revisions`;

const steps: Step[] = [
  {
    go: BOOK,
    target: { css: `${tid("chapters")} a`, text: "The Crossing" },
    act: { click: true },
    wait: { css: `${tid("editor")} .cm-line`, text: "tidecall" },
    say: "Open “The Crossing”, the first chapter of The Ferryman's Daughter.",
  },
  {
    target: { css: tid("save-status") },
    say: "Quarry saves as you write and says so here. Until the server has it, the text is also kept on this device, so a closed tab or a lost signal loses nothing.",
  },
  {
    target: { css: ".chapter-tools button", text: "History" },
    act: { click: true },
    wait: { css: tid("history") },
    say: "History keeps the chapter's earlier versions.",
    read: 1400,
  },
  {
    target: { css: revisions },
    say: "A snapshot is kept when you pause, leave the chapter or press Ctrl+S. This chapter has a few days of them.",
  },
  {
    target: { css: `${revisions} button`, nth: 2 },
    act: { click: true },
    wait: { css: ".revision-view" },
    say: "Choose an older one to see what changed since, word by word, or to read it on its own.",
  },
  {
    target: { css: `${tid("history")} button`, text: "Restore this version" },
    act: { click: true },
    wait: { css: ".notice", text: "Restored" },
    say: "Restore this version brings it back into the editor.",
  },
  {
    target: { css: ".chapter-tools button", text: "History" },
    act: { click: true },
    wait: { css: `${revisions} button`, text: "Before restoring" },
    say: "The text it replaced went into History first, so a restore can be undone the same way.",
  },
  {
    go: "/w/{w}",
    target: { css: tid("export") },
    say: "Export downloads the whole world as a zip of plain Markdown: chapters, bible, journal, decisions, and each book compiled in one file. It reads fine without Quarry.",
  },
  {
    go: "/new-world",
    target: { css: "section.card", text: "Or restore a world" },
    say: "Restore reads such a zip back in as a new world, without changing any you have.",
  },
  {
    go: "/settings",
    target: { css: tid("offline-settings") },
    say: "Settings: the world you last opened is copied to this device with its recent snapshots, so you can write and look back offline. What you write is sent when you're back.",
  },
  {
    target: { css: "section.card", text: "Passkeys" },
    say: "You sign in with a passkey, one per device, and no password. Add the phone's from the phone.",
  },
  {
    target: { css: "section.card", text: "Recovery codes" },
    say: "Recovery codes sign you in once each if every passkey is lost. Keep them somewhere apart from your devices.",
  },
  {
    go: "/w/{w}/settings",
    target: { css: `${tid("delete-world")} button`, text: "Delete this world" },
    act: { click: true },
    wait: { css: "#delete-name" },
    say: "Deleting a world is kept out of the way, in World settings.",
  },
  {
    target: { css: `${tid("delete-world")} button[type="submit"]` },
    say: "Delete forever stays off until the world's exact name is typed. Export it first if you might want it back.",
  },
  {
    target: { css: `${tid("delete-world")} button`, text: "Cancel" },
    act: { click: true },
    wait: { css: `${tid("delete-world")} button`, text: "Delete this world" },
    say: "Cancel. This sandbox stays until the next walkthrough replaces it.",
  },
];

export const safe: Tour = {
  id: "safe",
  title: "Keeping it safe",
  blurb: "Autosave and History, Export and Restore, the offline copy, passkeys and recovery codes, and deleting a world.",
  minutes: 2,
  covers: ["History and restore", "Export", "Restore", "Offline copy", "Passkeys"],
  steps,
};
