// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { tid } from "./common";

const steps: Step[] = [
  {
    go: "/w/{w}",
    phone: "/w/{w}/capture",
    in: "phone",
    target: { css: "#capture-body" },
    say: "On the phone, Quarry opens on Capture: one box for whatever just occurred to you, wherever you are.",
  },
  {
    in: "phone",
    target: { css: "#capture-body" },
    act: { fill: "What if the abbey bell rings by itself the night before every flood?" },
    say: "Type it.",
    read: 800,
  },
  {
    in: "phone",
    target: { css: '[aria-label="Belongs to"] button', text: "The Ferryman's Daughter" },
    act: { click: true },
    say: "Say which book it's for, or leave it for the whole world. The choice sticks for next time.",
  },
  {
    in: "phone",
    target: { css: ".capture-save" },
    act: { click: true },
    wait: { css: tid("capture-status") },
    say: "Save. Without a connection it waits on the phone and is sent when you're back.",
  },
  {
    phone: false,
    go: "/w/{w}/inbox",
    target: { css: `${tid("inbox-list")} .item-head`, text: "abbey bell" },
    say: "At the desk, it's in the inbox with everything else waiting to be sorted.",
  },
  {
    target: { css: `${tid("inbox-list")} .item-head`, text: "abbey bell" },
    act: { click: true },
    wait: { css: `${tid("inbox-list")} .item.open` },
    say: "Open it.",
    read: 900,
  },
  {
    target: { css: `${tid("inbox-list")} .item.open input[type="text"]` },
    act: { fill: "The bell rings before floods: it goes in chapter 2" },
    say: "Closing it can leave a one-line decision. Optional, and it goes in the Decisions log.",
  },
  {
    target: { css: `${tid("inbox-list")} .item.open button`, text: "Accept" },
    act: { click: true },
    say: "Accept, reject, harvest into something else, or defer for later. Every close can be undone.",
  },
  {
    go: "/w/{w}/triage",
    target: { css: ".triage-keys" },
    say: "Triage sorts the inbox one item at a time from the keyboard: a, r, h and d, with u to undo.",
  },
  {
    go: "/w/{w}/decisions",
    target: { css: "li", text: "The bell rings before floods" },
    say: "And the decision is in the log, dated, next to the earlier ones.",
  },
];

export const capture: Tour = {
  id: "capture",
  title: "A spark on the phone, sorted at the desk",
  blurb: "Capture on the phone, then the inbox, closing with a decision, and Triage.",
  minutes: 2,
  covers: ["Capture", "Inbox", "Triage", "Decisions"],
  steps,
};
