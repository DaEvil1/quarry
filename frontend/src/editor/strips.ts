// The small things that open beside a word: a name's card, a misspelling's quick fixes, and the strip for a selection.
// Plain DOM, so they appear instantly inside the editor. Buttons keep the keyboard in the text (mousedown is
// cancelled), so using one never moves the cursor or interrupts typing.

import { ENTITY_KINDS, type EntityKind, type EntityRef } from "../types";
import type { Card } from "../world/cards";
import { isPronunciation } from "../world/labels";
import { possessors, shownByName, speciesText } from "../world/species";

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
  // as of this chapter (docs/SPEC.md §13.2.4)
  if (card.age) who.append(el("span", "qcard-age", card.age));
  // what a character is, as of this chapter: "selkie · appears as human" (docs/SPEC.md §13.3)
  const kinds = speciesText(card);
  if (kinds) who.append(el("span", "qcard-species", kinds));
  head.append(who, el("span", `qkind k-${card.kind}`, kindLabel(card.kind)));
  root.append(head);
  const held = possessors(card);
  if (held.length) {
    const line = el("div", "qcard-possessed");
    line.append("possessed by ");
    held.forEach((p, i) => line.append(...(i ? [", "] : []), el("span", `qname k-${p.kind}`, p.name)));
    root.append(line);
  }
  if (card.summary) root.append(el("div", "qcard-summary", card.summary));
  // an event's time, tinted by its era (docs/SPEC.md §13.2.1)
  if (card.whenText) root.append(el("div", `qcard-when era-tint${card.whenColour ? ` era-${card.whenColour}` : ""}`, card.whenText));
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
  const rels = card.relations.filter((r) => !shownByName(r));
  if (rels.length) {
    const ul = el("ul", "qcard-rels");
    for (const r of rels.slice(0, 4)) {
      const li = el("li");
      li.append(`${r.label} `, el("span", `qname k-${r.other.kind}`, r.other.name));
      if (r.role) li.append(el("span", "qcard-role", ` · ${r.role}`));
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

/** Selected words: make them a bible entry of some kind, or another name of an entry; or record them as an event. */
export function selectionStripDom(
  text: string,
  names: EntityRef[],
  actions: { create: (kind: EntityKind) => unknown; addName: (id: string) => unknown; done: () => void; cut?: () => unknown; history?: HistoryActions },
): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "selection-strip";
  const main = el("div", "qrow");
  if (actions.cut) main.append(chip("Cut to bin", actions.cut, "quiet"));
  const history = actions.history;
  if (history) main.append(chip("Record as event", () => recordForm(root, history, actions.done), "quiet"));
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

// ---- recording history from the prose (docs/SPEC.md §13.2.3) -----------------------------------------------------

/** What the passage strip needs from the chapter page: the names in the selection, the events to offer, and saving. */
export interface HistoryActions {
  /** the entries named in the selection (found by the matcher that colours names), in order */
  named: EntityRef[];
  /** events to offer, those named in the selection and the chapter first */
  events: () => EntityRef[];
  /** the entries already related to an event */
  relatedTo: (eventId: string) => Set<string>;
  /** an event's own time in words, and its number (to tell a different one) */
  eventWhen: (eventId: string) => { text: string; at: number | null } | null;
  /** this chapter's own time, when it is a tale or a flashback with one */
  chapterTime: { text: string; at: number; approx: boolean } | null;
  /** a tale or flashback with no time of its own */
  untimed: boolean;
  record: (r: { eventId?: string; name?: string; taking: { id: string; role: "involved" | "place" }[]; when: { at: number; approx: boolean } | null; choice: "keep" | "use" }) => Promise<unknown>;
  /** where a character's birth and death are recorded now (a chapter's title), if they are */
  life: (id: string) => { born: string | null; died: string | null };
  setLife: (id: string, which: "born" | "died") => Promise<unknown>;
  setChapterTime: () => void;
}

const parseNumber = (t: string) => {
  const v = t.trim().replace("−", "-");
  return /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : null;
};

/** A passage selected: cut it to the bin, record it as an event, or set a birth or a death here. */
export function passageStripDom(actions: { cut?: () => unknown; history?: HistoryActions; done: () => void }): HTMLElement {
  const root = el("div", "qstrip passage-strip");
  root.dataset.testid = "passage-strip";
  const main = el("div", "qrow");
  if (actions.cut) main.append(chip("Cut to bin", actions.cut, "quiet"));
  const h = actions.history;
  if (h) {
    main.append(chip("Record as event", () => recordForm(root, h, actions.done), "primary"));
    root.append(main);
    lifeChips(root, h);
  } else root.append(main);
  return root;
}

/** "Seyla: born here · died here", for each character named in the selection. */
function lifeChips(root: HTMLElement, h: HistoryActions) {
  const people = h.named.filter((n) => n.kind === "character");
  for (const p of people) {
    const row = el("div", "qrow life-row");
    row.dataset.testid = "life-chips";
    const life = h.life(p.id);
    row.append(el("span", `qname k-${p.kind}`, p.name), ": ");
    const one = (which: "born" | "died", label: string) => {
      const was = life[which];
      if (was) {
        row.append(el("span", "qcard-also", `${p.name} is recorded ${which} in “${was}” · `));
        row.append(chip("Move it here", async () => {
          await h.setLife(p.id, which);
          row.replaceChildren(el("span", "qcard-also", `${p.name}: ${which} here.`));
        }));
      } else {
        row.append(chip(label, async () => {
          await h.setLife(p.id, which);
          row.replaceChildren(el("span", "qcard-also", `${p.name}: ${which} here.`));
        }));
      }
    };
    one("born", "born here");
    row.append(" · ");
    one("died", "died here");
    root.append(row);
    if (h.untimed) {
      const note = el("div", "qcard-also untimed-note");
      note.append(`This chapter has no time yet: ${p.name} will count as born before the story begins · `);
      note.append(chip("Set its time…", h.setChapterTime, "quiet"));
      root.append(note);
    }
  }
}

/** The strip grows into a small form in place, as "Another name of…" does: the event, who and where, when; Enter
 * saves, Esc goes straight back to the text. */
function recordForm(root: HTMLElement, h: HistoryActions, done: () => void) {
  root.replaceChildren();
  root.dataset.testid = "record-form";
  let picked: EntityRef | null = null;
  let choice: "keep" | "use" = "keep";
  // 1. the event: a new one by name, or one that exists (those named here first)
  const name = el("input", "qinput");
  name.placeholder = "The event: a new name, or pick one";
  name.setAttribute("aria-label", "Event");
  const list = el("div", "qlist");
  const renderEvents = () => {
    const q = name.value.trim().toLowerCase();
    list.replaceChildren(
      ...h
        .events()
        .filter((e) => !q || e.name.toLowerCase().includes(q))
        .slice(0, 5)
        .map((e) =>
          chip(e.name, () => {
            picked = e;
            name.value = e.name;
            list.replaceChildren(el("span", "qcard-also", "an event in the bible"));
            renderWho();
            renderWhen();
          }, picked?.id === e.id ? "k-event on" : "k-event"),
        ),
    );
  };
  name.addEventListener("input", () => {
    picked = null;
    renderEvents();
    renderWho();
    renderWhen();
  });
  // 2. who and where: a chip per entry named here; characters, factions and species ticked, the first place as where
  const who = el("div", "qrow who-chips");
  who.dataset.testid = "record-who";
  const ticked = new Map<string, "involved" | "place" | null>();
  let firstPlace = true;
  for (const n of h.named) {
    if (n.kind === "place") {
      ticked.set(n.id, firstPlace ? "place" : null);
      firstPlace = false;
    } else ticked.set(n.id, ["character", "faction", "species"].includes(n.kind) ? "involved" : null);
  }
  const renderWho = () => {
    const already = picked ? h.relatedTo(picked.id) : new Set<string>();
    who.replaceChildren(
      ...h.named.map((n) => {
        const label = el("label", `qchip k-${n.kind} who-chip`);
        const box = el("input");
        box.type = "checkbox";
        box.checked = !!ticked.get(n.id);
        box.addEventListener("change", () => ticked.set(n.id, box.checked ? (n.kind === "place" ? "place" : "involved") : null));
        label.append(box, ` ${n.name}${n.kind === "place" ? " (where)" : ""}${already.has(n.id) ? " · related already" : ""}`);
        return label;
      }),
    );
    if (!h.named.length) who.append(el("span", "qcard-also", "No names from the bible in the selection."));
  };
  // 3. when: a number (and about), empty to set later; a tale's own time is one chip away
  const whenRow = el("div", "qrow");
  const at = el("input", "qinput time-num");
  at.placeholder = "when (optional)";
  at.setAttribute("aria-label", "When");
  at.inputMode = "decimal";
  const aboutBox = el("input");
  aboutBox.type = "checkbox";
  aboutBox.setAttribute("aria-label", "About");
  const aboutLabel = el("label", "qcard-also");
  aboutLabel.append(aboutBox, " about");
  const conflict = el("div", "qrow");
  const renderWhen = () => {
    conflict.replaceChildren();
    const own = picked ? h.eventWhen(picked.id) : null;
    const given = parseNumber(at.value);
    if (own && own.at !== null && given !== null && given !== own.at) {
      conflict.append(
        chip(`Keep ${own.text}`, () => ((choice = "keep"), conflict.querySelectorAll(".qchip").forEach((c, i) => c.classList.toggle("on", i === 0))), choice === "keep" ? "on" : ""),
        chip(`Use ${at.value.trim()}`, () => ((choice = "use"), conflict.querySelectorAll(".qchip").forEach((c, i) => c.classList.toggle("on", i === 1))), choice === "use" ? "on" : ""),
      );
    }
  };
  at.addEventListener("input", renderWhen);
  whenRow.append(at, aboutLabel);
  if (h.chapterTime) {
    const t = h.chapterTime;
    whenRow.append(chip(`This chapter's time (${t.text})`, () => {
      at.value = String(t.at);
      aboutBox.checked = t.approx;
      renderWhen();
    }, "quiet"));
  }
  // 4. save
  const save = async () => {
    const typed = name.value.trim();
    if (!picked && !typed) {
      name.focus();
      return;
    }
    const n = parseNumber(at.value);
    await h.record({
      eventId: picked?.id,
      name: picked ? undefined : typed,
      taking: [...ticked].filter(([, r]) => r).map(([id, r]) => ({ id, role: r! })),
      when: n === null ? null : { at: n, approx: aboutBox.checked },
      choice,
    });
    done();
  };
  const row = el("div", "qrow");
  row.append(chip("Save", save, "primary"), chip("Cancel", done, "quiet"));
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      done();
    } else if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT" && (e.target as HTMLInputElement).type !== "checkbox") {
      e.preventDefault();
      void save();
    }
  });
  root.append(el("span", "qstrip-q", "Record as event"), name, list, who, whenRow, conflict, row);
  renderEvents();
  renderWho();
  setTimeout(() => name.focus());
}
