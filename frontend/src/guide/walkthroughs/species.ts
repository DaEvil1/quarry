// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { tid } from "./common";

const ROLE = `${tid("labels-roles")} details[data-role="Warden-Captain"]`;

const steps: Step[] = [
  {
    go: "/w/{w}",
    target: { css: tid("nav-kind-species") },
    act: { click: true },
    wait: { css: `${tid("bible-list")} a.kname`, text: "marsh-wight" },
    say: "A species is an entry like any other. The delta has three: human, dog, and the marsh-wights of the reed beds.",
  },
  {
    target: { css: `${tid("bible-list")} a.kname`, text: "marsh-wight" },
    act: { click: true },
    wait: { css: tid("relationship"), text: "The Ninefold Delta" },
    say: "Open the marsh-wight. Its facts describe it: a spirit, sapient, living longer than the abbey.",
  },
  {
    target: { css: tid("relationship"), text: "The Ninefold Delta" },
    say: "“Native to” ties a species to the place it comes from: the Ninefold Delta.",
  },
  {
    target: { css: tid("nav-kind-character") },
    act: { click: true },
    wait: { css: `${tid("bible-list")} th`, text: "Species" },
    say: "Back to the characters.",
    read: 900,
  },
  {
    target: { css: `${tid("bible-list")} th`, text: "Species" },
    say: "Once any character is recorded as being a species, the table gets a Species column. Click a value in it to list only those.",
  },
  {
    target: { css: tid("group-by") },
    act: { choose: "@species" },
    wait: { css: tid("section-marsh-wight") },
    say: "Or group the table by species.",
    read: 1000,
  },
  {
    target: { css: tid("section-marsh-wight") },
    say: "Brother Cade is the only marsh-wight. Nobody at Saltreach asks him how old he is.",
  },
  {
    target: { css: tid("section-dog") },
    say: "Moss is a dog, recorded the same way.",
  },
  {
    target: { css: `${tid("section-marsh-wight")} a.kname`, text: "Brother Cade" },
    act: { click: true },
    wait: { css: tid("species-words") },
    say: "Open Brother Cade.",
    read: 900,
  },
  {
    target: { css: tid("species-words") },
    say: "Beside his name: a marsh-wight that appears as human. Two relationships say so, “is a” and “appears as”, and either can change partway through the story.",
  },
  {
    go: "/w/{w}/bible/labels",
    target: { css: `${ROLE} > summary` },
    act: { click: true },
    wait: { css: `${ROLE} ${tid("switch-one-at-a-time")}` },
    say: "A role is a part someone holds in a group: the River Wardens have a Warden-Captain. Roles are listed at the end of the Labels page.",
  },
  {
    target: { css: `${ROLE} .switches` },
    say: "Warden-Captain is marked one at a time: the Wardens can only have one at once.",
  },
  {
    target: { css: `${ROLE} a.kname`, text: "The River Wardens" },
    act: { click: true },
    wait: { css: tid("relationship"), text: "Harl Brenner" },
    say: "Open the River Wardens.",
    read: 900,
  },
  {
    target: { css: tid("relationship"), text: "Harl Brenner" },
    say: "Ilse Marrow leads them as Warden-Captain. Harl Brenner was a lock-keeper until The Locks, and Warden-Captain from then on.",
  },
  {
    target: { css: tid("nav-checks") },
    act: { click: true },
    wait: { css: tid("check"), text: "Warden-Captain" },
    say: "Nobody recorded Ilse stepping down. Checks compares what is recorded.",
  },
  {
    target: { css: tid("check"), text: "Warden-Captain" },
    say: "Two Warden-Captains in The Locks. One of them is a mistake, or a handover nobody wrote down.",
  },
  {
    target: { css: `${tid("check")} ${tid("end-before")}` },
    act: { click: true },
    say: "If it was a handover, one click ends Ilse's time as Warden-Captain where Harl's begins, and the finding goes.",
  },
];

export const species: Tour = {
  id: "species",
  title: "Species and roles",
  blurb: "Species as entries, what a character is and appears as, roles held one at a time, and the clash in Checks.",
  minutes: 2,
  covers: ["Species", "Is a / appears as", "Species column", "Roles", "Checks"],
  steps,
};
