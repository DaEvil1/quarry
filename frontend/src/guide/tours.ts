// The Guide's walkthroughs (docs/SPEC.md §15), each a few minutes on the sandbox copy of the demo world. They lean on
// what the demo plants (backend/src/quarry/demo.py) and on the data-testids the e2e tests use, so the e2e run that
// plays every walkthrough (e2e/guide.spec.ts) catches one that has gone stale.

import type { Step, Tour } from "./engine";

const BOOK = "/w/{w}/p/the-ferrymans-daughter";
const tid = (id: string) => `[data-testid="${id}"]`;

const timeline: Step[] = [
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
    target: { css: `${tid("timeline")} [data-testid="mark"]`, text: "compass argument" },
    say: "The new event sits in year 392, between the raising of the locks and the book.",
  },
  {
    target: { css: tid("book-band") },
    say: "The books sit where their chapters are set.",
  },
  {
    target: { css: tid("fold") },
    say: "Long empty stretches fold up, so a few centuries don't swallow the page. Scroll on the page to zoom in.",
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

const experiments: Step[] = [
  {
    go: "/w/{w}/p/ash-season",
    target: { css: tid("experiment-row") },
    say: "An experiment is another draft of one or more chapters. The book doesn't change while you try it. Ash Season has one across its first two chapters.",
  },
  {
    target: { css: `${tid("experiment-row")} button` },
    act: { click: true },
    wait: { css: tid("experiment") },
    say: "Open it.",
    read: 1200,
  },
  {
    target: { css: tid("drafts") },
    say: "Each draft is a chapter of its own, written in the same editor. These two began as copies of the chapters they would replace.",
  },
  {
    target: { css: tid("read-as-if") },
    act: { click: true },
    wait: { css: tid("read-as-if-line") },
    say: "Read as if accepted: the whole book with the drafts in place, to judge it as a reader would.",
  },
  {
    target: { css: tid("read-as-if-line") },
    say: "The line at the top says which experiment you are reading.",
  },
  {
    go: BOOK,
    target: { css: '[aria-label="Pick chapter 3"]' },
    act: { click: true },
    wait: { css: tid("selection-bar") },
    say: "Now one of your own. In The Ferryman's Daughter, pick chapter 3…",
  },
  {
    target: { css: '[aria-label="Pick chapter 4"]' },
    act: { click: true, shift: true },
    wait: { css: tid("selection-bar"), text: "Chapters 3–4" },
    say: "…and shift-click chapter 4 to take both.",
  },
  {
    target: { css: tid("start-experiment") },
    act: { click: true },
    wait: { css: tid("start-form") },
    say: "Start an experiment over them.",
    read: 1200,
  },
  {
    target: { css: "#exp-title" },
    act: { fill: "Cade tells it" },
    say: "Give it a working title. Starting from copies means revising rather than a blank page.",
  },
  {
    target: { css: `${tid("start-form")} button[type="submit"]` },
    act: { click: true },
    wait: { css: tid("experiment"), text: "Cade tells it" },
    say: "Start.",
    read: 900,
  },
  {
    target: { css: tid("drafts") },
    say: "Two drafts, copied from chapters 3 and 4. Rewrite them as much as you like; the book stays as it was.",
  },
  {
    target: { css: `${tid("experiment")} ${tid("accept")}` },
    act: { click: true },
    wait: { css: tid("retire-review") },
    say: "Happy with it? Accept puts the drafts in the book. First, a short review.",
  },
  {
    target: { css: tid("retire-review") },
    say: "What is tied to the chapters being retired is listed here: facts, relationships, where people are. Keep, move or drop each one. Nothing goes quietly.",
  },
  {
    target: { css: `${tid("retire-review")} input[placeholder="a harvest note"]` },
    act: { fill: "Tamsin alone with the compass in the guest room" },
    say: "One line per chapter on what was alive in it, for Salvage. Optional.",
  },
  {
    target: { css: tid("review-confirm") },
    act: { click: true },
    wait: { css: ".toast", text: "Accepted" },
    say: "Confirm.",
    read: 900,
  },
  {
    target: { css: ".toast", text: "Accepted" },
    say: "The drafts are chapters 3 and 4 now. Changed your mind? Undo puts it all back, the review too.",
  },
  {
    go: `${BOOK}/salvage`,
    target: { css: tid("salvage-entry"), text: "What the River Kept" },
    say: "The old chapters wait in Salvage with their harvest notes. They can be searched, and copied into a later experiment.",
  },
];

const capture: Step[] = [
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

export const TOURS: Tour[] = [
  {
    id: "capture",
    title: "A spark on the phone, sorted at the desk",
    blurb: "Capture on the phone, then the inbox, closing with a decision, and Triage.",
    minutes: 2,
    covers: ["Capture", "Inbox", "Triage", "Decisions"],
    steps: capture,
  },
  {
    id: "timeline",
    title: "Story time and the Timeline",
    blurb: "When chapters are set, recording an event from a passage, and reading the Timeline.",
    minutes: 4,
    covers: ["When a chapter is set", "Record as event", "Timeline", "Checks"],
    steps: timeline,
  },
  {
    id: "experiments",
    title: "Restructuring with experiments",
    blurb: "Trying other drafts of a range of chapters, reading them in place, accepting, and Salvage.",
    minutes: 4,
    covers: ["Experiments", "Read as if accepted", "The review", "Salvage"],
    steps: experiments,
  },
];

/** The walkthroughs still to write, so the Guide page shows the whole map. */
export const LATER: { title: string; covers: string }[] = [
  { title: "Getting back in", covers: "The front page, where you stopped, the Writing and Planning focus" },
  { title: "Writing a chapter with the companion", covers: "Names by kind, margin notes, the five tabs, F8 and Alt+Enter, stashing" },
  { title: "The bible", covers: "Entries and kinds, other names, the name check, labels, book-only entries" },
  { title: "Facts and relationships from the prose", covers: "Record a fact, as of a chapter, where everyone is, the family tree" },
  { title: "Species and roles", covers: "Is a, appears as, one Warden-Captain at a time" },
  { title: "Revising", covers: "Cuts bin, word history, changes since a checkpoint, find and replace, an entry's thread" },
  { title: "Planning in the Journal", covers: "World tools in a journal entry, planned facts, loose ends, Include planned" },
  { title: "The chart", covers: "Places drawn from the bible, pins, scrubbing through time" },
  { title: "Names shared by two entries", covers: "The two Linnets, choice lines, the shared card" },
  { title: "Keeping it safe", covers: "Export, Restore, the offline copy, passkeys and recovery codes" },
];
