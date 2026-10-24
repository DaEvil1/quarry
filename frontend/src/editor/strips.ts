// The small things that open beside a word: a name's card, a misspelling's quick fixes, and the strip for a selection.
// Plain DOM, so they appear instantly inside the editor. Buttons keep the keyboard in the text (mousedown is
// cancelled), so using one never moves the cursor or interrupts typing.

import { ENTITY_KINDS, type EntityKind, type EntityRef } from "../types";
import type { Card } from "../world/cards";
import { isPronunciation } from "../world/labels";

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", text = ""): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}

function chip(label: string, onClick: () => unknown, cls = ""): HTMLButtonElement {
  const b = el("button", `qchip ${cls}`.trim(), label);
  b.type = "button";
  b.addEventListener("mousedown", (e) => e.preventDefault());
  b.addEventListener("click", async (e) => {
    e.preventDefault();
    b.disabled = true;
    try {
      await onClick();
    } finally {
      b.disabled = false;
    }
  });
  return b;
}

const kindLabel = (k: string) => ENTITY_KINDS.find((x) => x.value === k)?.label ?? k;
/** A name in a picker, with the book whose bible it is in when that isn't this chapter's (docs/SPEC.md §12.4). */
const labelled = (n: EntityRef & { where?: string }) => (n.where ? `${n.name} · ${n.where}` : n.name);

/** A name's card: the one-liner, a few facts and relationships, and two actions. */
/** Recording a relationship from a name's card: who or what with, then how. */
export interface LinkActions {
  names: () => EntityRef[];
  /** the ways this entry can be related to `other`, as they read from this entry */
  options: (other: EntityRef) => { key: string; reads: string }[];
  add: (other: EntityRef, key: string) => Promise<unknown>;
}

/** Where a character is in this chapter ("is at"). */
export interface IsAtActions {
  here: () => EntityRef | null;
  /** places to offer, the ones named in this chapter first */
  places: () => EntityRef[];
  set: (place: EntityRef) => Promise<unknown>;
}

export function cardDom(
  card: Card | undefined,
  actions: { open: () => void; notHere?: () => unknown; link?: LinkActions; isAt?: IsAtActions; several?: (kind: string, label: string) => boolean },
): HTMLElement {
  const root = el("div", "qcard");
  root.setAttribute("role", "tooltip");
  root.dataset.testid = "name-card";
  if (!card) {
    root.append(el("div", "qcard-summary", "Loading…"));
    return root;
  }
  const head = el("div", "qcard-head");
  // after the name, small: how it is said, and a character's gender when set (an unset field adds nothing)
  const said = card.facts.find((f) => isPronunciation(f.label) && f.value.trim());
  const who = el("span", "qcard-name");
  who.append(el("strong", "", card.name));
  if (said) who.append(el("span", "qcard-said", said.value));
  if (card.kind === "character" && card.gender) who.append(el("span", "qcard-gender", card.gender));
  head.append(who, el("span", `qkind k-${card.kind}`, kindLabel(card.kind)));
  root.append(head);
  if (card.summary) root.append(el("div", "qcard-summary", card.summary));
  if (card.aliases.length) root.append(el("div", "qcard-also", `also ${card.aliases.join(", ")}`));
  // the first few facts; a label that holds several values shows them as chips side by side
  const facts: { label: string; values: string[]; several: boolean }[] = [];
  for (const f of card.facts) {
    if (isPronunciation(f.label)) continue;
    const several = !!actions.several?.(card.kind, f.label);
    const row = several ? facts.find((x) => x.several && x.label.toLowerCase() === f.label.toLowerCase()) : undefined;
    if (row) row.values.push(f.value);
    else facts.push({ label: f.label, values: [f.value], several });
  }
  if (facts.length) {
    const dl = el("dl", "qcard-facts");
    for (const f of facts.slice(0, 4)) {
      const dd = el("dd", "", f.several ? "" : f.values[0] || "—");
      if (f.several) for (const v of f.values) dd.append(el("span", "qcard-chip", v || "—"));
      dl.append(el("dt", "", f.label), dd);
    }
    root.append(dl);
  }
  if (card.relations.length) {
    const ul = el("ul", "qcard-rels");
    for (const r of card.relations.slice(0, 4)) {
      const li = el("li");
      li.append(`${r.label} `, el("span", `qname k-${r.other.kind}`, r.other.name));
      if (r.standing !== "canon") li.append(el("span", "qcard-standing", ` (${r.standing})`));
      ul.append(li);
    }
    root.append(ul);
  }
  const row = el("div", "qrow");
  const isAt = card.kind === "character" ? actions.isAt : undefined;
  const here = isAt?.here();
  if (here) {
    const line = el("div", "qcard-here");
    line.append("Here: ", el("span", `qname k-${here.kind}`, here.name));
    root.append(line);
  }
  row.append(chip("Open", actions.open));
  if (isAt) row.append(chip(here ? "Moved…" : "Is at…", () => isAtFlow(row, card, isAt)));
  const link = actions.link;
  if (link) row.append(chip("Link to…", () => linkFlow(row, card, link)));
  if (actions.notHere) row.append(chip("Not a name here", actions.notHere, "quiet"));
  root.append(row);
  return root;
}

/** In place of the card's buttons: the place this character is at in this chapter. */
function isAtFlow(row: HTMLElement, card: Card, isAt: IsAtActions) {
  const box = el("input", "qinput");
  box.placeholder = `${card.name} is at…`;
  box.setAttribute("aria-label", "Is at");
  const list = el("div", "qlist");
  const render = () => {
    const q = box.value.trim().toLowerCase();
    list.replaceChildren(
      ...isAt
        .places()
        .filter((p) => !q || p.name.toLowerCase().includes(q))
        .slice(0, 6)
        .map((p) =>
          chip(labelled(p), async () => {
            await isAt.set(p);
            row.replaceChildren(el("span", "qcard-also", `${card.name} is at ${p.name} in this chapter.`));
          }, `k-${p.kind}`),
        ),
    );
  };
  box.addEventListener("input", render);
  box.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      (list.firstElementChild as HTMLButtonElement | null)?.click();
    }
  });
  render();
  row.replaceChildren(box, list);
  setTimeout(() => box.focus());
}

/** In place of the card's buttons: a name to link to, then the relationship as chips. */
function linkFlow(row: HTMLElement, card: Card, link: LinkActions) {
  const box = el("input", "qinput");
  box.placeholder = `Link ${card.name} to…`;
  box.setAttribute("aria-label", "Link to");
  const list = el("div", "qlist");
  const pickName = (other: EntityRef) => {
    list.replaceChildren();
    box.remove();
    const head = el("div", "qcard-also");
    head.append(`${card.name} … `, el("span", `qname k-${other.kind}`, other.name));
    const opts = el("div", "qrow");
    for (const o of link.options(other)) {
      opts.append(
        chip(o.reads, async () => {
          await link.add(other, o.key);
          row.replaceChildren(el("span", "qcard-also", `Linked: ${o.reads} ${other.name}.`));
        }),
      );
    }
    row.replaceChildren(head, opts);
  };
  const render = () => {
    const q = box.value.trim().toLowerCase();
    list.replaceChildren(
      ...link
        .names()
        .filter((n) => n.id !== card.id && (!q || n.name.toLowerCase().includes(q)))
        .slice(0, 6)
        .map((n) => chip(labelled(n), () => pickName(n), `k-${n.kind}`)),
    );
  };
  box.addEventListener("input", render);
  box.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      (list.firstElementChild as HTMLButtonElement | null)?.click();
    }
  });
  render();
  row.replaceChildren(box, list);
  setTimeout(() => box.focus());
}

/** A likely misspelling: replace it, keep it as another spelling, or never flag it again. */
export function nearMissStripDom(
  word: string,
  name: string,
  actions: { replace: () => void; spelling: () => unknown; ignore: () => unknown },
): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "near-miss-strip";
  root.append(el("span", "qstrip-q", `${name}?`));
  root.append(chip(`Replace with ${name}`, actions.replace, "primary"), chip("Another spelling", actions.spelling), chip("Not a typo", actions.ignore));
  void word;
  return root;
}

/** Selected words: make them a bible entry of some kind, or another name of an entry. */
export function selectionStripDom(
  text: string,
  names: EntityRef[],
  actions: { create: (kind: EntityKind) => unknown; addName: (id: string) => unknown; done: () => void; cut?: () => unknown },
): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "selection-strip";
  const main = el("div", "qrow");
  if (actions.cut) main.append(chip("Cut to bin", actions.cut, "quiet"));
  const common: EntityKind[] = ["character", "place", "faction", "object"];
  for (const k of common) main.append(chip(`+ ${kindLabel(k)}`, () => actions.create(k), `k-${k}`));
  const more = chip("More…", () => {
    more.remove();
    for (const k of ENTITY_KINDS.map((x) => x.value).filter((k) => !common.includes(k))) {
      main.insertBefore(chip(`+ ${kindLabel(k)}`, () => actions.create(k), `k-${k}`), other);
    }
  }, "quiet");
  const other = chip("Another name of…", () => {
    main.replaceChildren();
    const box = el("input", "qinput");
    box.placeholder = `“${text}” is another name of…`;
    box.setAttribute("aria-label", "Entry");
    const list = el("div", "qlist");
    const render = () => {
      const q = box.value.trim().toLowerCase();
      list.replaceChildren(
        ...names
          .filter((n) => !q || n.name.toLowerCase().includes(q))
          .slice(0, 6)
          .map((n) => chip(labelled(n), () => actions.addName(n.id), `k-${n.kind}`)),
      );
    };
    box.addEventListener("input", render);
    box.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        (list.firstElementChild as HTMLButtonElement | null)?.click();
      } else if (e.key === "Escape") {
        e.preventDefault();
        actions.done();
      }
    });
    render();
    main.append(box, list);
    setTimeout(() => box.focus());
  }, "quiet");
  main.append(more, other);
  root.append(main);
  return root;
}

/** A passage selected (on a phone): cut it to the project's bin. */
export function cutStripDom(cut: () => unknown): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "cut-strip";
  root.append(chip("Cut to bin", cut, "primary"));
  return root;
}

/** Changes since a checkpoint: what stood here then. */
export function wasDom(was: string): HTMLElement {
  const root = el("div", "qstrip qwas");
  root.dataset.testid = "was";
  const text = was.trim();
  root.append(el("span", "qstrip-q", "Was:"), el("span", "qwas-text", text.length > 400 ? `${text.slice(0, 400)}…` : text));
  return root;
}

/** What a finding mark offers: its fix, adding a new name, another spelling, or leaving it be. */
export interface FindingActions {
  fix?: { label: string; run: () => unknown };
  /** a possible new name: make it an entry of a kind, or say it isn't a name */
  create?: (kind: EntityKind) => unknown;
  notAName?: () => unknown;
  /** a spelling worth adding to an entry */
  addSpelling?: { name: string; run: () => unknown };
  /** never flag this again */
  leave?: () => unknown;
}

export function findingStripDom(message: string, actions: FindingActions): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "finding-strip";
  root.append(el("span", "qstrip-q", message));
  const row = el("div", "qrow");
  if (actions.fix) row.append(chip(actions.fix.label, actions.fix.run, "primary"));
  if (actions.create) {
    const create = actions.create;
    for (const k of ["character", "place", "faction", "object"] as EntityKind[]) row.append(chip(`+ ${kindLabel(k)}`, () => create(k), `k-${k}`));
    const more = chip("More…", () => {
      more.remove();
      for (const k of ENTITY_KINDS.map((x) => x.value).filter((k) => !["character", "place", "faction", "object"].includes(k))) {
        row.insertBefore(chip(`+ ${kindLabel(k)}`, () => create(k), `k-${k}`), notName ?? null);
      }
    }, "quiet");
    row.append(more);
  }
  const notName = actions.notAName ? chip("Not a name", actions.notAName, "quiet") : null;
  if (notName) row.append(notName);
  if (actions.addSpelling) row.append(chip(`Another spelling of ${actions.addSpelling.name}`, actions.addSpelling.run));
  if (actions.leave) row.append(chip("Leave it", actions.leave, "quiet"));
  root.append(row);
  return root;
}
