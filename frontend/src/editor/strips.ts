// The small things that open beside a word: a name's card, a misspelling's quick fixes, and the strip for a selection.
// Plain DOM, so they appear instantly inside the editor. Buttons keep the keyboard in the text (mousedown is
// cancelled), so using one never moves the cursor or interrupts typing.

import { ENTITY_KINDS, type EntityKind, type EntityRef } from "../types";
import type { Card } from "../world/cards";

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

/** A name's card: the one-liner, a few facts and relationships, and two actions. */
export function cardDom(card: Card | undefined, actions: { open: () => void; notHere?: () => unknown }): HTMLElement {
  const root = el("div", "qcard");
  root.setAttribute("role", "tooltip");
  root.dataset.testid = "name-card";
  if (!card) {
    root.append(el("div", "qcard-summary", "Loading…"));
    return root;
  }
  const head = el("div", "qcard-head");
  head.append(el("strong", "", card.name), el("span", `qkind k-${card.kind}`, kindLabel(card.kind)));
  root.append(head);
  if (card.summary) root.append(el("div", "qcard-summary", card.summary));
  if (card.aliases.length) root.append(el("div", "qcard-also", `also ${card.aliases.join(", ")}`));
  if (card.facts.length) {
    const dl = el("dl", "qcard-facts");
    for (const f of card.facts.slice(0, 4)) dl.append(el("dt", "", f.label), el("dd", "", f.value || "—"));
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
  row.append(chip("Open", actions.open));
  if (actions.notHere) row.append(chip("Not a name here", actions.notHere, "quiet"));
  root.append(row);
  return root;
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
  actions: { create: (kind: EntityKind) => unknown; addName: (id: string) => unknown; done: () => void },
): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "selection-strip";
  const main = el("div", "qrow");
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
          .map((n) => chip(n.name, () => actions.addName(n.id), `k-${n.kind}`)),
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
