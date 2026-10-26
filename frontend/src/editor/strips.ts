// The small things that open beside a word: a name's card, a misspelling's quick fixes, and the strip for a selection.
// Plain DOM, so they appear instantly inside the editor. Buttons keep the keyboard in the text (mousedown is
// cancelled), so using one never moves the cursor or interrupts typing.

import { pictureUrl } from "../pictures";
import { ENTITY_KINDS, type EntityKind, type EntityRef } from "../types";
import type { Card } from "../world/cards";
import { shortNames } from "../world/cast";
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
  // its main picture's thumb, cropped to its middle, in the corner (docs/SPEC.md §17.2)
  if (card.picture) {
    const img = document.createElement("img");
    img.className = "qcard-pic";
    img.src = pictureUrl(card.picture, "thumb");
    img.alt = "";
    img.loading = "lazy";
    img.dataset.testid = "card-picture";
    img.addEventListener("error", () => img.remove());
    head.append(img);
  }
  root.append(head);
  // an entry of more than one kind: the main kind's colour, and what else it is (docs/SPEC.md §14.8)
  if (card.also_kinds?.length) root.append(el("div", "qcard-also", `also a ${card.also_kinds.map((k) => kindLabel(k).toLowerCase()).join(", ")}`));
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
  const facts: { label: string; values: string[]; several: boolean; planned: boolean }[] = [];
  for (const f of card.facts) {
    if (isPronunciation(f.label)) continue;
    const several = !!actions.several?.(card.kind, f.label);
    const planned = !!f.planned;
    const row = several ? facts.find((x) => x.several && x.planned === planned && x.label.toLowerCase() === f.label.toLowerCase()) : undefined;
    if (row) row.values.push(f.value);
    else facts.push({ label: f.label, values: [f.value], several, planned });
  }
  if (facts.length) {
    const dl = el("dl", "qcard-facts");
    // canon first, then planned (marked): a card in the Journal shows both (docs/SPEC.md §14.1.1)
    for (const f of [...facts.filter((x) => !x.planned).slice(0, 4), ...facts.filter((x) => x.planned).slice(0, 3)]) {
      const dd = el("dd", "", f.several ? "" : f.values[0] || "—");
      if (f.several) for (const v of f.values) dd.append(el("span", "qcard-chip", v || "—"));
      if (f.planned) dd.append(el("span", "qcard-standing", " planned"));
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
  actions: { create: (kind: EntityKind) => unknown; addName: (id: string) => unknown; done: () => void; cut?: () => unknown; history?: HistoryActions; passage?: PassageActions },
): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "selection-strip";
  const main = el("div", "qrow");
  if (actions.cut) main.append(chip("Cut to bin", actions.cut, "quiet"));
  const history = actions.history;
  if (history) main.append(chip("Record as event", () => recordForm(root, history, actions.done), "quiet"));
  if (actions.passage) passageChips(main, root, actions.passage, actions.done);
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
  /** where a character's birth and death are recorded now (a chapter's title), if they are; not in the Journal, where
   * there is no "here" */
  life?: (id: string) => { born: string | null; died: string | null };
  setLife: (id: string, which: "born" | "died") => Promise<unknown>;
  setChapterTime: () => void;
}

const parseNumber = (t: string) => {
  const v = t.trim().replace("−", "-");
  return /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : null;
};

/** A passage selected: cut it to the bin, record a fact or an event from it, make it a spark or a question, or set a
 * birth or a death here. */
export function passageStripDom(actions: { cut?: () => unknown; history?: HistoryActions; passage?: PassageActions; done: () => void }): HTMLElement {
  const root = el("div", "qstrip passage-strip");
  root.dataset.testid = "passage-strip";
  const main = el("div", "qrow");
  if (actions.cut) main.append(chip("Cut to bin", actions.cut, "quiet"));
  if (actions.passage) passageChips(main, root, actions.passage, actions.done);
  const h = actions.history;
  if (h) {
    main.append(chip("Record as event", () => recordForm(root, h, actions.done), "primary"));
    root.append(main);
    if (h.life) lifeChips(root, h);
  } else root.append(main);
  return root;
}

/** "Seyla: born here · died here", for each character named in the selection. */
function lifeChips(root: HTMLElement, h: HistoryActions) {
  const people = h.named.filter((n) => n.kind === "character");
  for (const p of people) {
    const row = el("div", "qrow life-row");
    row.dataset.testid = "life-chips";
    const life = h.life!(p.id);
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

// ---- a passage becomes a fact, a spark or a question (docs/SPEC.md §14.1.2, §14.3.1) ------------------------------

/** What recording from a selected passage needs from the page: the names in it, suggestions, and saving. */
export interface PassageActions {
  /** a chapter's passage or a journal entry's: what a fact's standing and span start on */
  where: "chapter" | "journal";
  /** the entries named in the selection, in order */
  named: EntityRef[];
  /** every entry, for "Other…" */
  names: () => EntityRef[];
  /** label suggestions for a kind, and value suggestions for a label (docs/SPEC.md §12.6) */
  labels: (kind: EntityKind) => string[];
  values: (kind: EntityKind, label: string) => string[];
  /** in a chapter: what is there already as planned (a fact with the same label), to make canon here instead */
  planned?: (entityId: string, label: string) => Promise<{ id: string; value: string; where: string } | null>;
  /** in a plan beside its chapter: that chapter, offered for when a fact holds, used only after a click (§18.4) */
  beside?: { id: string; label: string };
  /** in a plan: its chapters, as chips on a spark, question or task, and whether each starts ticked (§18.4) */
  chapters?: { id: string; label: string; ticked: boolean }[];
  recordFact: (f: {
    entity: EntityRef;
    label: string;
    value: string;
    span: { here: boolean; from: number | null; until: number | null; fromChapter?: string; untilChapter?: string };
    standing: "canon" | "planned";
    makeCanon?: string;
  }) => Promise<unknown>;
  saveItem: (i: { kind: "spark" | "question" | "task"; line: string; entities: string[]; park: boolean; chapters: string[] }) => Promise<unknown>;
}

/** The chips a selection offers for passage actions. */
export function passageChips(row: HTMLElement, root: HTMLElement, p: PassageActions, done: () => void) {
  row.append(
    chip("Record a fact", () => factForm(root, p, done), "quiet"),
    chip("Spark", () => itemForm(root, p, "spark", done), "quiet"),
    chip("Question", () => itemForm(root, p, "question", done), "quiet"),
  );
}

/** A choice of chips, one on. */
function choices<T extends string>(options: { value: T; label: string }[], start: T): { row: HTMLElement; value: () => T } {
  const row = el("div", "qrow");
  let current = start;
  const draw = () =>
    row.replaceChildren(
      ...options.map((o) => {
        const c = chip(o.label, () => {
          current = o.value;
          draw();
        }, current === o.value ? "on" : "");
        c.setAttribute("aria-pressed", String(current === o.value));
        return c;
      }),
    );
  draw();
  return { row, value: () => current };
}

/** Esc goes straight back to the text; Enter in a text box saves. */
function formKeys(root: HTMLElement, save: () => unknown, done: () => void) {
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      done();
    } else if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT" && (e.target as HTMLInputElement).type !== "checkbox") {
      e.preventDefault();
      void save();
    }
  });
}

/** Suggestions under a text box: chips that fill it in. */
function suggest(box: HTMLInputElement, list: HTMLElement, all: () => string[], picked: () => void) {
  const render = () => {
    const q = box.value.trim().toLowerCase();
    list.replaceChildren(
      ...all()
        .filter((s) => s.toLowerCase() !== q && (!q || s.toLowerCase().includes(q)))
        .slice(0, 6)
        .map((s) =>
          chip(s, () => {
            box.value = s;
            list.replaceChildren();
            picked();
          }, "quiet"),
        ),
    );
  };
  box.addEventListener("input", render);
  box.addEventListener("focus", render);
  return render;
}

const timeNumber = (t: string) => {
  const v = t.trim().replace("−", "-");
  return /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : null;
};

/** Record a fact: the entry, label and value, when it holds, standing; Enter saves. In a chapter, a fact planned
 * before with the same label is offered to be made canon here instead of a second one. */
function factForm(root: HTMLElement, p: PassageActions, done: () => void) {
  root.replaceChildren();
  root.dataset.testid = "fact-form";
  let entity: EntityRef | null = p.named[0] ?? null;
  // 1. the entry: a chip for each named in the selection (the first chosen), or another
  const who = el("div", "qrow");
  who.dataset.testid = "fact-entry";
  const choose = (n: EntityRef) => {
    entity = n;
    drawWho();
    void checkPlanned();
  };
  const drawWho = () => {
    const other = entity && !p.named.some((n) => n.id === entity!.id) ? entity : null;
    who.replaceChildren(
      ...p.named.map((n) => chip(n.name, () => choose(n), `k-${n.kind}${entity?.id === n.id ? " on" : ""}`)),
      other ? chip(other.name, () => undefined, `k-${other.kind} on`) : chip("Other…", pickOther, "quiet"),
    );
  };
  const pickOther = () => {
    const box = el("input", "qinput");
    box.placeholder = "Which entry?";
    box.setAttribute("aria-label", "Entry");
    const list = el("div", "qlist");
    const render = () => {
      const q = box.value.trim().toLowerCase();
      list.replaceChildren(
        ...p
          .names()
          .filter((n) => !q || n.name.toLowerCase().includes(q))
          .slice(0, 6)
          .map((n) => chip(labelled(n), () => choose(n), `k-${n.kind}`)),
      );
    };
    box.addEventListener("input", render);
    render();
    who.replaceChildren(box, list);
    setTimeout(() => box.focus());
  };
  // 2. label and value, with the suggestions of §12.6
  const label = el("input", "qinput");
  label.placeholder = "label (status, age …)";
  label.setAttribute("aria-label", "Label");
  const labels = el("div", "qlist");
  const value = el("input", "qinput");
  value.placeholder = "value";
  value.setAttribute("aria-label", "Value");
  const values = el("div", "qlist");
  suggest(label, labels, () => (entity ? p.labels(entity.kind) : []), () => {
    void checkPlanned();
    value.focus();
  });
  suggest(value, values, () => (entity && label.value.trim() ? p.values(entity.kind, label.value.trim()) : []), () => value.focus());
  label.addEventListener("change", () => void checkPlanned());
  // 3. when it holds: in a chapter from this chapter (or throughout); a time on either side instead
  // in a plan beside its chapter: that chapter is offered, and used only after a click (docs/SPEC.md §18.4)
  const span = choices<"here" | "throughout" | "fromBeside" | "untilBeside">(
    p.where === "chapter"
      ? [{ value: "here", label: "from this chapter" }, { value: "throughout", label: "throughout" }]
      : [
          { value: "throughout", label: "holds throughout" },
          ...(p.beside ? [{ value: "fromBeside" as const, label: `from ${p.beside.label}` }, { value: "untilBeside" as const, label: `until ${p.beside.label}` }] : []),
        ],
    p.where === "chapter" ? "here" : "throughout",
  );
  if (p.beside) span.row.prepend(el("span", "qcard-also", "The chapter beside:"));
  span.row.dataset.testid = "fact-span";
  const from = el("input", "qinput time-num");
  from.placeholder = "from (time)";
  from.setAttribute("aria-label", "From time");
  from.inputMode = "decimal";
  const until = el("input", "qinput time-num");
  until.placeholder = "until (time)";
  until.setAttribute("aria-label", "Until time");
  until.inputMode = "decimal";
  const when = el("div", "qrow");
  when.append(span.row, from, until);
  // 4. standing: planned until it is in the book or marked canon (Thomas, docs/SPEC.md §14.1.2)
  const standing = choices<"canon" | "planned">([{ value: "canon", label: "canon" }, { value: "planned", label: "planned" }], p.where === "chapter" ? "canon" : "planned");
  standing.row.dataset.testid = "fact-standing";
  // make it canon here, when it is there as planned already
  const plannedRow = el("div", "qrow");
  plannedRow.dataset.testid = "planned-here";
  let plannedId: string | null = null;
  let asNew = false;
  let asked = 0;
  const checkPlanned = async () => {
    const ask = ++asked;
    plannedId = null;
    asNew = false;
    plannedRow.replaceChildren();
    const l = label.value.trim();
    if (!p.planned || !entity || !l) return;
    const found = await p.planned(entity.id, l).catch(() => null);
    if (ask !== asked || !found) return;
    plannedId = found.id;
    plannedRow.append(
      el("span", "qcard-also", `Planned: ${l} ${found.value} (${found.where}) · `),
      chip("Make it canon here", () => save(), "primary"),
      chip("Record a new one", () => {
        asNew = true;
        plannedRow.replaceChildren(el("span", "qcard-also", "A new fact, beside the planned one."));
      }),
    );
  };
  // 5. save (Enter)
  const save = async () => {
    const l = label.value.trim();
    if (!entity) return;
    if (!l) {
      label.focus();
      return;
    }
    const fromT = timeNumber(from.value);
    await p.recordFact({
      entity,
      label: l,
      value: value.value.trim(),
      span: {
        here: span.value() === "here" && fromT === null, from: fromT, until: timeNumber(until.value),
        ...(p.beside && span.value() === "fromBeside" ? { fromChapter: p.beside.id } : {}),
        ...(p.beside && span.value() === "untilBeside" ? { untilChapter: p.beside.id } : {}),
      },
      standing: standing.value(),
      makeCanon: plannedId && !asNew ? plannedId : undefined,
    });
    done();
  };
  const row = el("div", "qrow");
  row.append(chip("Save", save, "primary"), chip("Cancel", done, "quiet"));
  formKeys(root, save, done);
  root.append(el("span", "qstrip-q", "Record a fact"), who, label, labels, value, values, when, standing.row, plannedRow, row);
  drawWho();
  if (!entity) pickOther();
  else setTimeout(() => label.focus());
}

/** A spark, question or task from the passage: kind, a line of your own (optional), the entries named, park it. */
function itemForm(root: HTMLElement, p: PassageActions, start: "spark" | "question", done: () => void) {
  root.replaceChildren();
  root.dataset.testid = "item-form";
  const kind = choices<"spark" | "question" | "task">(
    [{ value: "spark", label: "spark" }, { value: "question", label: "question" }, { value: "task", label: "task" }],
    start,
  );
  kind.row.dataset.testid = "item-kind";
  const line = el("input", "qinput");
  line.placeholder = "A line of your own (optional)";
  line.setAttribute("aria-label", "Your line");
  const ticked = new Set(p.named.map((n) => n.id));
  const who = el("div", "qrow who-chips");
  for (const n of p.named) {
    const label = el("label", `qchip k-${n.kind} who-chip`);
    const box = el("input");
    box.type = "checkbox";
    box.checked = true;
    box.addEventListener("change", () => (box.checked ? ticked.add(n.id) : ticked.delete(n.id)));
    label.append(box, ` ${n.name}`);
    who.append(label);
  }
  // in a plan: its chapters, ticked as the page says (the one beside; the only one), so it shows in their Loose ends
  const forChapters = new Set((p.chapters ?? []).filter((c) => c.ticked).map((c) => c.id));
  const chaptersRow = el("div", "qrow who-chips");
  chaptersRow.dataset.testid = "item-chapters";
  for (const c of p.chapters ?? []) {
    const label = el("label", "qchip who-chip");
    const box = el("input");
    box.type = "checkbox";
    box.checked = c.ticked;
    box.addEventListener("change", () => (box.checked ? forChapters.add(c.id) : forChapters.delete(c.id)));
    label.append(box, ` ${c.label}`);
    chaptersRow.append(label);
  }
  const parkLabel = el("label", "qchip quiet");
  const park = el("input");
  park.type = "checkbox";
  parkLabel.append(park, " Park it");
  const save = async () => {
    await p.saveItem({ kind: kind.value(), line: line.value.trim(), entities: [...ticked], park: park.checked, chapters: [...forChapters] });
    done();
  };
  const row = el("div", "qrow");
  row.append(parkLabel, chip("Save", save, "primary"), chip("Cancel", done, "quiet"));
  formKeys(root, save, done);
  root.append(el("span", "qstrip-q", "From this passage"), kind.row, line, who, ...(p.chapters?.length ? [chaptersRow] : []), row);
  setTimeout(() => line.focus());
}

// ---- a name shared by two entries (docs/SPEC.md §14.10) -----------------------------------------------------------

export interface SharedActions {
  /** from here on, the name means these entries (null: nobody in particular) */
  choose: (ids: string[] | null) => unknown;
  open: (id: string) => void;
}

/** "From here: Marr · Senn · Both", without the ones already chosen; Unsure once something is. */
function fromHere(claimants: Card[], chosen: string[] | null, actions: SharedActions): HTMLElement {
  const row = el("div", "qrow");
  row.dataset.testid = "shared-strip";
  row.append(el("span", "qstrip-q", "From here:"));
  const short = shortNames(claimants.map((c) => c.name));
  const ids = claimants.map((c) => c.id);
  claimants.forEach((c, i) => {
    if (chosen?.length === 1 && chosen[0] === c.id) return;
    row.append(chip(short[i], () => actions.choose([c.id]), `k-${c.kind}`));
  });
  if (!(chosen && chosen.length === ids.length)) row.append(chip(claimants.length === 2 ? "Both" : "All", () => actions.choose(ids)));
  if (chosen) row.append(chip("Unsure", () => actions.choose(null), "quiet"));
  return row;
}

/** A shared name no choice line settles: everyone claiming it with their one-liner, then which one it means from here. */
export function sharedCardDom(form: string, claimants: Card[], actions: SharedActions): HTMLElement {
  const root = el("div", "qcard");
  root.setAttribute("role", "tooltip");
  root.dataset.testid = "shared-card";
  const head = el("div", "qcard-head");
  head.append(el("span", "qcard-name", `${form}?`), el("span", "qcard-also", `${claimants.length} entries share it`));
  root.append(head);
  const ul = el("ul", "qcard-rels");
  for (const c of claimants) {
    const li = el("li");
    const name = el("button", `qname k-${c.kind} qlink`, c.name);
    name.type = "button";
    name.addEventListener("mousedown", (e) => e.preventDefault());
    name.addEventListener("click", () => actions.open(c.id));
    li.append(name);
    if (c.summary) li.append(el("span", "qcard-role", ` · ${c.summary}`));
    ul.append(li);
  }
  const choose = fromHere(claimants, null, actions);
  // the keyboard (Alt+Enter, F8) starts on the first choice
  const first = choose.querySelector("button");
  if (first) first.dataset.first = "";
  root.append(ul, choose);
  return root;
}

/** A shared name a choice line settled: the chosen entry's card, then the others, Both and Unsure. */
export function settledRow(card: HTMLElement, claimants: Card[], chosen: string[], actions: SharedActions): HTMLElement {
  card.append(fromHere(claimants, chosen, actions));
  return card;
}

/** A choice line whose words single out nobody: the claimants to put in instead. */
export function badChoiceStripDom(form: string, claimants: Card[], put: (id: string) => unknown): HTMLElement {
  const root = el("div", "qstrip");
  root.dataset.testid = "choice-strip";
  root.append(el("span", "qstrip-q", `Which ${form}?`));
  for (const c of claimants) root.append(chip(c.name, () => put(c.id), `k-${c.kind}`));
  return root;
}
