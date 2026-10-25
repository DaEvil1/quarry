// What the writing companion finds in a chapter's text (docs/WORLD-MODEL.md §7), worked out in the browser so it is
// live and works offline. Rules only: nothing here suggests story content or rewrites a sentence. The Continuity
// checks are over recorded data and come from the server.

import { ENTITY_KINDS, type EntityRef, type Presence } from "../types";
import type { Card } from "./cards";
import { missingKey, missingLabels } from "./labels";
import type { Hit, Matcher } from "./matcher";
import { markers } from "./markers";

export type EditorName = "proofreader" | "continuity" | "connections" | "archivist" | "looseEnds";

export const EDITORS: { name: EditorName; label: string; about: string }[] = [
  { name: "proofreader", label: "Proofreader", about: "doubled words, the same word close together, spacing, likely misspelled names" },
  { name: "continuity", label: "Continuity", about: "dead but named, before being born, conflicting facts, point of view, places inside themselves" },
  { name: "connections", label: "Connections", about: "names that share a sentence or paragraph with no recorded link, and where people are" },
  { name: "archivist", label: "Archivist", about: "possible new names, entries without a one-liner, spellings worth adding, expected labels, entries of another book's bible, evidence in Salvage" },
  { name: "looseEnds", label: "Loose ends", about: "TK and ?? markers, margin notes, items made from or stashed in this text, your note for next time" },
];

export type Strength = "strong" | "medium" | "weak";

export interface Finding {
  editor: EditorName;
  rule: string;
  /** stable within the rule, for resolving it ("intentional", "not connected") */
  key: string;
  message: string;
  /** where in the text, to jump to (and to mark, while Revising) */
  from?: number;
  to?: number;
  strength?: Strength;
  /** a fix that only changes this spot of text */
  fix?: { from: number; to: number; insert: string; label: string };
  a?: EntityRef;
  b?: EntityRef;
  word?: string;
  places?: EntityRef[];
  /** an expected label the entry hasn't got */
  label?: string;
  /** evidence resting on a retired chapter: what it is, and where its passage is found now */
  evidence?: { kind: "fact" | "relationship" | "telling"; id: string; found: { id: string; title: string }[] };
}

export interface AnalyseInput {
  text: string;
  matcher: Matcher;
  card: (id: string) => Card | undefined;
  /** pairs with a recorded relationship (either way round, any time) */
  linked: Set<string>;
  presence: Presence[];
  /** resolved findings, as "rule|key" */
  resolved: Set<string>;
  /** flag sentences longer than this many words (0: off) */
  longSentence: number;
  /** the chapter's project (its slug), and a project's name by its slug */
  project?: string;
  projectName?: (slug: string) => string;
  /** the labels expected on every entry of a kind */
  expected?: (kind: string) => string[];
  /** evidence resting on passages in retired chapters, from the server (docs/SPEC.md §13.6.3) */
  evidence?: { key: string; kind: "fact" | "relationship" | "telling"; id: string; message: string; entities: EntityRef[]; found: { id: string; title: string }[] }[];
  /** a journal entry, not a chapter (docs/SPEC.md §14.1.1): a %% line is ordinary text there, and "is at" is per
   * chapter, so there is no "Where are they?" */
  journal?: boolean;
}

const pairKey = (a: string, b: string) => (a < b ? `${a}:${b}` : `${b}:${a}`);
export const linkKey = pairKey;

const MARGIN = /^[ \t]*%%[^\n]*/gm;
/** The chapter without its margin notes (%% lines), every other character where it was. */
export const storyText = (text: string) => text.replace(MARGIN, (m) => " ".repeat(m.length));

const WORD = /[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu;
const STOP = new Set(
  ("the a an and or but of to in on at by for with from as is was were be been are it its he she they them his her " +
    "their there this that these those not no so then than had has have do did does would could should will can " +
    "into out up down over under again very just only what when where who whom which while said says").split(" "),
);
// capitalised words that are not names
const NOT_NAMES = new Set(
  ("I I'm I'll I'd I've Mr Mrs Ms Dr Sir Madam Lord Lady King Queen Captain Mother Father God OK " +
    "Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August " +
    "September October November December").split(" "),
);
const DOUBLED_OK = new Set(["had", "that"]);

/** Sentence and paragraph boundaries, so a position can be placed. */
class Layout {
  sentenceEnds: number[] = [];
  lineStarts: number[] = [0];
  constructor(text: string) {
    const ends = /[.!?…]+["'”’)\]]*(?=\s|$)|\n/g;
    for (let m = ends.exec(text); m; m = ends.exec(text)) this.sentenceEnds.push(m.index + m[0].length);
    for (let i = text.indexOf("\n"); i >= 0; i = text.indexOf("\n", i + 1)) this.lineStarts.push(i + 1);
  }
  private static bisect(xs: number[], at: number): number {
    let lo = 0;
    let hi = xs.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (xs[mid]! <= at) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }
  sentence(at: number): number {
    return Layout.bisect(this.sentenceEnds, at);
  }
  paragraph(at: number): number {
    return Layout.bisect(this.lineStarts, at) - 1;
  }
}

/** Does a sentence start at `at`? (only quotes, brackets and dashes between it and the last full stop or line start) */
function startsSentence(text: string, at: number): boolean {
  let i = at - 1;
  while (i >= 0 && /[\s"'“‘(\[—–-]/.test(text[i]!)) {
    if (text[i] === "\n") return true;
    i--;
  }
  return i < 0 || /[.!?…:]/.test(text[i]!);
}

/** The words around a spot, within its own line (at most 60 characters). */
function lineAround(text: string, at: number): string {
  const start = text.lastIndexOf("\n", at - 1) + 1;
  const end = text.indexOf("\n", at);
  const line = text.slice(start, end < 0 ? text.length : end);
  const i = at - start;
  return line.slice(Math.max(0, i - 30), i + 30).trim();
}

const around = (text: string, from: number, to: number) => text.slice(Math.max(0, from - 12), to + 12).replace(/\s+/g, " ").trim().toLowerCase();

export function analyse(input: AnalyseInput): Finding[] {
  const text = input.journal ? input.text : storyText(input.text);
  const layout = new Layout(text);
  const out: Finding[] = [];
  const keep = (f: Finding) => {
    if (!input.resolved.has(`${f.rule}|${f.key}`)) out.push(f);
  };
  const hits: Hit[] = [];
  for (let i = 0; i < layout.lineStarts.length; i++) {
    const start = layout.lineStarts[i]!;
    const end = i + 1 < layout.lineStarts.length ? layout.lineStarts[i + 1]! - 1 : text.length;
    hits.push(...input.matcher.scanLine(text.slice(start, end), start, true));
  }
  const names = hits.filter((h) => h.kind !== "near_miss");
  // which characters of the text belong to a name (a lookup per word, not a search through every name)
  const nameMask = new Uint8Array(text.length + 1);
  for (const h of hits) nameMask.fill(1, h.start, h.end);
  const inName = (at: number) => nameMask[at] === 1;
  const ref = (id: string): EntityRef => {
    const c = input.card(id);
    return { id, name: c?.name ?? "?", kind: c?.kind ?? "other" };
  };

  // ---- Proofreader ----
  const doubled = /(?<![\p{L}\p{N}'’])([\p{L}'’]+)([ \t]+)\1(?![\p{L}\p{N}'’])/giu;
  for (let m = doubled.exec(text); m; m = doubled.exec(text)) {
    if (DOUBLED_OK.has(m[1]!.toLowerCase())) continue;
    const second = m.index + m[1]!.length;
    const again = m[0].slice(m[1]!.length).trim();
    keep({ editor: "proofreader", rule: "doubled", key: around(text, m.index, m.index + m[0].length), from: m.index, to: m.index + m[0].length,
      message: `“${m[1]} ${again}”: the word twice.`, fix: { from: second, to: m.index + m[0].length, insert: "", label: `Remove the second “${again}”` } });
  }
  for (const [re, what, fix] of [
    [/(?<=\S)[ \t]{2,}(?=\S)/g, "Two spaces", " "],
    [/[ \t]+(?=[,.;:!?](?:\s|$))/g, "A space before punctuation", ""],
  ] as const) {
    for (let m = re.exec(text); m; m = re.exec(text)) {
      keep({ editor: "proofreader", rule: "spacing", key: around(text, m.index, m.index + m[0].length), from: m.index, to: m.index + m[0].length,
        message: `${what}.`, fix: { from: m.index, to: m.index + m[0].length, insert: fix, label: "Fix the spacing" } });
    }
  }
  const noSpace = /([,;!?]|\.(?!\.))(?=[\p{Lu}][\p{Ll}])/gu;
  for (let m = noSpace.exec(text); m; m = noSpace.exec(text)) {
    const at = m.index + m[0].length;
    keep({ editor: "proofreader", rule: "spacing", key: around(text, m.index, at + 1), from: m.index, to: at + 1,
      message: "No space after punctuation.", fix: { from: at, to: at, insert: " ", label: "Add a space" } });
  }
  // the same word close together (within 12 words, in one paragraph), names and small words aside
  {
    const recent = new Map<string, { n: number; at: number; para: number }>();
    let n = 0;
    WORD.lastIndex = 0;
    for (let m = WORD.exec(text); m; m = WORD.exec(text)) {
      n++;
      const w = m[0].toLowerCase();
      if (w.length < 4 || STOP.has(w) || inName(m.index)) continue;
      const para = layout.paragraph(m.index);
      const prev = recent.get(w);
      if (prev && prev.para === para && n - prev.n <= 12 && n - prev.n > 1) {
        keep({ editor: "proofreader", rule: "echo", key: `${w}:${around(text, m.index, m.index + w.length)}`, from: m.index, to: m.index + m[0].length,
          message: `“${m[0]}” again, ${n - prev.n} words after the last one.`, word: m[0] });
      }
      recent.set(w, { n, at: m.index, para });
    }
  }
  if (input.longSentence > 0) {
    let start = 0;
    for (const end of layout.sentenceEnds.concat(text.length)) {
      const s = text.slice(start, end);
      const words = s.match(WORD)?.length ?? 0;
      if (words > input.longSentence) {
        const from = start + (s.length - s.trimStart().length);
        keep({ editor: "proofreader", rule: "long_sentence", key: around(text, from, from + 30), from, to: end,
          message: `A sentence of ${words} words.` });
      }
      start = end;
    }
  }
  for (const h of hits.filter((x) => x.kind === "near_miss")) {
    const target = ref(h.entityId);
    keep({ editor: "proofreader", rule: "near_miss", key: `${h.matched}:${h.entityId}`, from: h.start, to: h.end, word: h.matched, a: target,
      message: `“${h.matched}”: ${target.name}?`, fix: { from: h.start, to: h.end, insert: target.name, label: `Replace with ${target.name}` } });
  }

  // ---- Connections ----
  {
    // per sentence and per paragraph: who is named there, and where first
    const sentences = new Map<number, Map<string, Hit>>();
    const paragraphs = new Map<number, Map<string, Hit>>();
    const mentions = new Map<string, number>();
    const firstSeen = new Map<string, number>();
    const placesNear = new Map<string, Map<string, number>>();
    for (const h of names) {
      const s = layout.sentence(h.start);
      const p = layout.paragraph(h.start);
      if (!sentences.has(s)) sentences.set(s, new Map());
      if (!paragraphs.has(p)) paragraphs.set(p, new Map());
      if (!sentences.get(s)!.has(h.entityId)) sentences.get(s)!.set(h.entityId, h);
      if (!paragraphs.get(p)!.has(h.entityId)) paragraphs.get(p)!.set(h.entityId, h);
      mentions.set(h.entityId, (mentions.get(h.entityId) ?? 0) + 1);
      if (!firstSeen.has(h.entityId)) firstSeen.set(h.entityId, h.start);
    }
    // only the pairs that are actually together somewhere, with where they first are
    const strong = new Map<string, number>();
    const medium = new Map<string, number>();
    const at = new Map<string, Hit>();
    const count = (groups: Map<number, Map<string, Hit>>, into: Map<string, number>) => {
      for (const group of groups.values()) {
        const xs = [...group.values()];
        for (let i = 0; i < xs.length; i++) {
          for (let j = i + 1; j < xs.length; j++) {
            const key = pairKey(xs[i]!.entityId, xs[j]!.entityId);
            into.set(key, (into.get(key) ?? 0) + 1);
            if (!at.has(key)) at.set(key, xs[i]!.start > xs[j]!.start ? xs[i]! : xs[j]!);
          }
        }
      }
    };
    count(sentences, strong);
    count(paragraphs, medium);
    for (const group of paragraphs.values()) {
      const places = [...group.keys()].filter((id) => input.card(id)?.kind === "place");
      if (!places.length) continue;
      for (const id of group.keys()) {
        if (input.card(id)?.kind !== "character") continue;
        const m = placesNear.get(id) ?? new Map<string, number>();
        for (const p of places) m.set(p, (m.get(p) ?? 0) + 1);
        placesNear.set(id, m);
      }
    }
    // weak: only in the same chapter. With many names that is every pair, so only the most-named few
    const busiest = [...mentions].sort((x, y) => y[1] - x[1]).slice(0, 12).map(([id]) => id);
    const weak: string[] = [];
    for (let i = 0; i < busiest.length; i++) {
      for (let j = i + 1; j < busiest.length; j++) {
        const key = pairKey(busiest[i]!, busiest[j]!);
        if (!medium.has(key)) weak.push(key);
      }
    }
    const pairs = [...new Set([...medium.keys(), ...weak])].filter((key) => !input.linked.has(key));
    const found: Finding[] = [];
    for (const key of pairs) {
      // in the order they first appear, so "Varren and Isolde" reads the way the text does
      const [x, y] = key.split(":") as [string, string];
      const [a, b] = (firstSeen.get(x) ?? 0) <= (firstSeen.get(y) ?? 0) ? [ref(x), ref(y)] : [ref(y), ref(x)];
      const s = strong.get(key) ?? 0;
      const p = medium.get(key) ?? 0;
      const strength: Strength = s ? "strong" : p ? "medium" : "weak";
      const message = s
        ? `${a.name} and ${b.name} share a sentence${s > 1 ? ` ${s}×` : ""} here.`
        : p
          ? `${a.name} and ${b.name} are in the same paragraph${p > 1 ? ` ${p}×` : ""}.`
          : `${a.name} and ${b.name} are both in this chapter.`;
      const where = at.get(key);
      found.push({ editor: "connections", rule: "unrecorded", key, a, b, strength, message, from: where?.start, to: where?.end });
    }
    // strongest first, and within a strength the pairs seen together most often
    const order = { strong: 0, medium: 1, weak: 2 };
    const together = (f: Finding) => (strong.get(f.key) ?? 0) * 1000 + (medium.get(f.key) ?? 0);
    found.sort((x, y) => order[x.strength!] - order[y.strength!] || together(y) - together(x) || x.message.localeCompare(y.message));
    found.forEach(keep);
    // where are they: several places around them, none recorded
    const here = new Set(input.presence.map((p) => p.entity_id));
    for (const [id, places] of input.journal ? [] : placesNear) {
      if (places.size < 2 || here.has(id)) continue;
      const who = ref(id);
      keep({ editor: "connections", rule: "where", key: id, a: who, places: [...places].sort((x, y) => y[1] - x[1]).map(([p]) => ref(p)),
        message: `Where is ${who.name}? ${places.size} places are named around them, none recorded.` });
    }
  }

  // ---- Archivist ----
  {
    const seen = new Map<string, { total: number; inside: number; first: number }>();
    const cap = /(?<![\p{L}\p{N}'’-])\p{Lu}[\p{Ll}]+(?:['’-][\p{L}]+)*/gu;
    for (let m = cap.exec(text); m; m = cap.exec(text)) {
      const w = m[0].replace(/['’]s$/, "");
      if (w.length < 3 || NOT_NAMES.has(w) || STOP.has(w.toLowerCase()) || input.matcher.knows(w) || inName(m.index)) continue;
      const e = seen.get(w) ?? { total: 0, inside: 0, first: -1 };
      e.total++;
      if (!startsSentence(text, m.index)) {
        e.inside++;
        if (e.first < 0) e.first = m.index;
      }
      seen.set(w, e);
    }
    for (const [w, e] of seen) {
      if (e.total < 2 || e.inside < 1) continue;
      keep({ editor: "archivist", rule: "new_name", key: w, word: w, from: e.first, to: e.first + w.length,
        message: `“${w}” appears ${e.total}× and isn't in the bible.` });
    }
    const named = [...new Set(names.map((h) => h.entityId))];
    for (const id of named) {
      const c = input.card(id);
      if (c && !c.summary) keep({ editor: "archivist", rule: "no_summary", key: id, a: ref(id), message: `${c.name} has no one-line summary yet.` });
    }
    // an entry of another book's own bible, named in this one: share it with the world? (docs/SPEC.md §12.4)
    if (input.project) {
      for (const id of named) {
        const c = input.card(id);
        if (c?.project && c.project !== input.project) {
          keep({ editor: "archivist", rule: "crossover", key: `${id}:${input.project}`, a: ref(id),
            message: `${c.name} is in ${input.projectName?.(c.project) ?? c.project}'s bible and is named here.` });
        }
      }
    }
    // labels expected on every entry of its kind, missing (only labels marked expected: never inferred from use)
    if (input.expected) {
      for (const id of named) {
        const c = input.card(id);
        if (!c) continue;
        const plural = ENTITY_KINDS.find((k) => k.value === c.kind)?.plural.toLowerCase() ?? c.kind;
        for (const label of missingLabels(c, input.expected(c.kind))) {
          keep({ editor: "archivist", rule: "missing_label", key: missingKey(id, label), a: ref(id), label,
            message: `${c.name} has no ${label} (expected for ${plural}).` });
        }
      }
    }
    // evidence that rests on a passage in a retired chapter, for the entries named here
    for (const x of input.evidence ?? []) {
      const who = x.entities.find((e) => named.includes(e.id));
      if (who) keep({ editor: "archivist", rule: "evidence_retired", key: x.key, a: who, message: x.message, evidence: { kind: x.kind, id: x.id, found: x.found } });
    }
    const misses = new Map<string, { n: number; h: Hit }>();
    for (const h of hits.filter((x) => x.kind === "near_miss")) {
      const e = misses.get(h.matched) ?? { n: 0, h };
      e.n++;
      misses.set(h.matched, e);
    }
    for (const [w, { n, h }] of misses) {
      if (n < 2) continue;
      const target = ref(h.entityId);
      keep({ editor: "archivist", rule: "other_name", key: `${w}:${h.entityId}`, word: w, a: target, from: h.start, to: h.end,
        message: `“${w}” is written ${n}× here: another name for ${target.name}?` });
    }
  }

  // ---- Loose ends (from the text: the rest comes from the server) ----
  for (const m of markers(text)) {
    keep({ editor: "looseEnds", rule: m.kind === "tk" ? "tk" : "unsure", key: around(text, m.from, m.to), from: m.from, to: m.to,
      message: `${m.kind === "tk" ? "TK" : "??"}: ${lineAround(text, m.from)}` });
  }
  MARGIN.lastIndex = 0;
  for (let m = input.journal ? null : MARGIN.exec(input.text); m; m = MARGIN.exec(input.text)) {
    const note = m[0].replace(/^[ \t]*%%\s*/, "");
    keep({ editor: "looseEnds", rule: "margin", key: note.toLowerCase(), from: m.index, to: m.index + m[0].length, message: note || "(an empty margin note)" });
  }
  return out;
}
