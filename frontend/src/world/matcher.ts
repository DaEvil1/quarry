// Finding the world's names in text, in the browser, exactly as the server does (backend/src/quarry/mentions.py):
// names and other names on word boundaries with plural and possessive endings; capitals optional per entry; a
// character's first name (computed by the server); "not in this sense" phrases; and capitalised words one edit
// away from a name (two for long words, a swapped pair counting as one) as likely misspellings: a word that is a name
// by itself anywhere, a word of a longer name only with the rest of that name around it ("Old Harbor", not "Fears"
// for "The Lock Years"). A name two entries claim is shared (docs/SPEC.md §14.10): ambiguous until a choice line,
// `%% Isolde: Isolde Marr`, settles it.

import type { Card } from "./cards";

export interface Hit {
  start: number;
  end: number;
  /** for a shared name: the first claimant, or the first one chosen */
  entityId: string;
  /** exact | alias | near_miss; ambiguous for a shared name nothing has settled */
  kind: "exact" | "alias" | "near_miss" | "ambiguous";
  /** the entry's kind (character, place, …); for a shared name, the claimants' kind, or "name" when they differ */
  entityKind: string;
  matched: string;
  /** a shared name: its key (lowercase, as choice lines are matched), its form as written, and everyone claiming it */
  shared?: { key: string; ids: string[]; form: string };
  /** a shared name a choice line settled: the entries chosen (a mention of each) */
  chosen?: string[];
}

/** A choice line: from `end` on, the shared name `key` means `ids`, or nobody in particular (null). A line whose
 * words single out no claimant has no ids ([]) and changes nothing. */
export interface Choice {
  start: number;
  end: number;
  key: string;
  ids: string[] | null;
  /** everyone claiming the name, for offering them */
  owners: string[];
}

/** `%% Isolde: Isolde Marr`, `%% Isolde: Marr, Senn`, `%% Isolde: ?` (as on the server) */
const CHOICE = /^[ \t]*%%[ \t]*([^:\n]*[^:\s])[ \t]*:[ \t]*([^\n]*?)[ \t]*$/gm;
const MARGIN = /^[ \t]*%%[^\n]*/gm;

const SUFFIX = "(?:'s|’s|s)?";
const WORD = /(?<![\p{L}\p{N}_'’-])\p{L}[\p{L}\p{N}]*(?:['’-][\p{L}\p{N}]+)*/gu;
const POSSESSIVE = /(?:'s|’s)$/;
const NEAR_MIN = 5;
/** where a name ends: an optional plural or possessive, then no more of a word (as the name patterns end) */
const NAME_END = new RegExp(`${SUFFIX}(?![\\p{L}\\p{N}_])`, "uy");
const NAME_CHAR = /[\p{L}\p{N}_'’-]/u;
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Optimal string alignment distance: like Levenshtein, with a swapped pair of letters counting as one edit. */
export function osa(a: string, b: string, limit = 99): number {
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  // three rolling rows (two back, for the swapped pair) instead of a whole table: this runs for every capitalised
  // word against every name, so it must not allocate much
  let prev2 = new Uint16Array(b.length + 1);
  let prev = new Uint16Array(b.length + 1);
  let cur = new Uint16Array(b.length + 1);
  for (let j = 0; j <= b.length; j++) prev[j] = j;
  for (let i = 1; i <= a.length; i++) {
    cur[0] = i;
    let rowMin = i;
    const ai = a.charCodeAt(i - 1);
    for (let j = 1; j <= b.length; j++) {
      const bj = b.charCodeAt(j - 1);
      let v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ai === bj ? 0 : 1));
      if (i > 1 && j > 1 && ai === b.charCodeAt(j - 2) && a.charCodeAt(i - 2) === bj) v = Math.min(v, prev2[j - 2] + 1);
      cur[j] = v;
      if (v < rowMin) rowMin = v;
    }
    if (rowMin > limit) return limit + 1;
    [prev2, prev, cur] = [prev, cur, prev2];
  }
  return prev[b.length];
}

/** Whether text[start, end) stands where a word of a name does: `before` the rest of the name before it, `after` the
 * rest after it (lowercase for a name matched whatever the capitals), as on the server. */
export function fits(text: string, start: number, end: number, before: string, after: string, loose: boolean): boolean {
  if (before) {
    const i = start - before.length;
    const seg = i >= 0 ? text.slice(i, start) : "";
    if ((loose ? seg.toLowerCase() : seg) !== before || (i > 0 && NAME_CHAR.test(text[i - 1]))) return false;
  }
  if (after) {
    const j = end + after.length;
    const seg = text.slice(end, j);
    if ((loose ? seg.toLowerCase() : seg) !== after) return false;
    NAME_END.lastIndex = j;
    if (!NAME_END.test(text)) return false;
  }
  return true;
}

/** How many lines' results a matcher remembers (a long chapter has a few hundred paragraphs). */
const LINE_CACHE = 4000;

/** A name that starts with "The" also matches with "the" (mid-sentence), and the other way round, as on the server. */
export function articleForms(name: string): string[] {
  for (const [a, b] of [["The ", "the "], ["the ", "The "]] as const) {
    if (name.startsWith(a) && name.length > a.length) return [name, b + name.slice(a.length)];
  }
  return [name];
}

type Owner = [string, Hit["kind"]];
/** a use of a near-miss candidate: the entry, the rest of the name before and after the word (both empty for a
 * one-word name), and whether the name is matched whatever the capitals */
type Use = [string, string, string, boolean];

export class Matcher {
  /** every form, with the entries claiming it in the order met (a shared name has several) */
  private exact = new Map<string, Owner[]>();
  private loose = new Map<string, Owner[]>();
  private names = new Map<string, string>();
  private exactRe: RegExp | null;
  private looseRe: RegExp | null;
  private exclusions = new Map<string, string[]>();
  private kinds = new Map<string, string>();
  private knownLower = new Set<string>();
  /** each near-miss candidate's uses, in the order met */
  private uses = new Map<string, Use[]>();
  private ignored: Set<string>;
  /** the near-miss candidates by length, so a word is only compared with names it could be one or two edits from */
  private ownersByLength = new Map<number, string[]>();
  /** ties go to the name met first, as on the server */
  private ownerOrder = new Map<string, number>();
  /** a word's candidates: the words of names it could be a misspelling of, closest first */
  private nearCache = new Map<string, string[]>();
  /** a line's hits (at offset 0), so typing in one paragraph doesn't rescan the others */
  private lineCache = new Map<string, Hit[]>();

  constructor(cards: Card[], ignored: Iterable<string> = []) {
    const claim = (table: Map<string, Owner[]>, form: string, id: string, kind: Hit["kind"]) => {
      const owners = table.get(form);
      if (!owners) table.set(form, [[id, kind]]);
      else if (!owners.some(([o]) => o === id)) owners.push([id, kind]);
    };
    for (const c of cards) {
      this.kinds.set(c.id, c.kind);
      this.names.set(c.id, c.name);
      const forms: [string, Hit["kind"]][] = [[c.name, "exact"], ...c.aliases.map((a) => [a, "alias"] as [string, Hit["kind"]])];
      if (c.first_name) forms.push([c.first_name, "alias"]);
      for (const [raw, kind] of forms) {
        const f = raw.trim();
        if (!f) continue;
        if (c.match_case) {
          for (const v of articleForms(f)) claim(this.exact, v, c.id, kind);
        } else claim(this.loose, f.toLowerCase(), c.id, kind);
      }
      const ex = c.exclusions.map((x) => x.toLowerCase()).filter(Boolean);
      if (ex.length) this.exclusions.set(c.id, ex);
    }
    // an entry's own name is never shared: where it is also someone's other name or first name, the name wins
    for (const table of [this.exact, this.loose]) {
      for (const [form, owners] of table) {
        if (owners.length > 1 && owners.some(([, k]) => k === "exact")) table.set(form, owners.filter(([, k]) => k === "exact"));
      }
    }
    const alternation = (forms: Iterable<string>, flags: string) => {
      const list = [...forms].sort((a, b) => b.length - a.length);
      return list.length
        ? new RegExp(`(?<![\\p{L}\\p{N}_'’-])(${list.map(escape).join("|")})${SUFFIX}(?![\\p{L}\\p{N}_])`, flags)
        : null;
    };
    this.exactRe = alternation(this.exact.keys(), "gu");
    this.looseRe = alternation(this.loose.keys(), "giu");
    for (const [f, [[id]]] of [...this.exact, ...this.loose]) {
      for (const wm of f.matchAll(WORD)) {
        const w = wm[0];
        this.knownLower.add(w.toLowerCase());
        if (w.length >= NEAR_MIN) {
          const loose = !this.exact.has(f);
          const key = loose ? w[0].toUpperCase() + w.slice(1) : w;
          const use: Use = [id, f.slice(0, wm.index), f.slice(wm.index + w.length), loose];
          const uses = this.uses.get(key);
          if (!uses) this.uses.set(key, [use]);
          else if (!uses.some((u) => u.every((x, k) => x === use[k]))) uses.push(use);
        }
      }
    }
    this.ignored = new Set(ignored);
    let i = 0;
    for (const k of this.uses.keys()) {
      this.ownerOrder.set(k, i++);
      this.ownersByLength.set(k.length, [...(this.ownersByLength.get(k.length) ?? []), k]);
    }
  }

  /** Like scan, remembering each line's result: for the editor, which scans the lines on screen on every change. */
  scanLine(text: string, offset = 0, nearMisses = true): Hit[] {
    const key = `${nearMisses ? 1 : 0}${text}`;
    let hits = this.lineCache.get(key);
    if (!hits) {
      hits = this.scan(text, 0, nearMisses);
      if (this.lineCache.size >= LINE_CACHE) this.lineCache.clear();
      this.lineCache.set(key, hits);
    }
    return offset ? hits.map((h) => ({ ...h, start: h.start + offset, end: h.end + offset })) : hits;
  }

  /** The words of names `base` could be a misspelling of, closest first (the first met, of equally close ones). */
  private nearest(base: string): string[] {
    const known = this.nearCache.get(base);
    if (known !== undefined) return known;
    const limit = base.length <= 6 ? 1 : 2;
    const close: [number, number, string][] = [];
    for (let len = base.length - limit; len <= base.length + limit; len++) {
      for (const cand of this.ownersByLength.get(len) ?? []) {
        const d = osa(base, cand, limit);
        if (d <= limit) close.push([d, this.ownerOrder.get(cand)!, cand]);
      }
    }
    const found = close.sort((a, b) => a[0] - b[0] || a[1] - b[1]).map(([, , c]) => c);
    if (this.nearCache.size > 20_000) this.nearCache.clear();
    this.nearCache.set(base, found);
    return found;
  }

  /** The entry the word text[start, end) is likely a misspelling of, if any: the closest candidate that, here, stands
   * where it would in a name. */
  private nearMiss(text: string, start: number, end: number): string | null {
    for (const w of this.nearest(text.slice(start, end))) {
      for (const [id, before, after, loose] of this.uses.get(w)!) if (fits(text, start, end, before, after, loose)) return id;
    }
    return null;
  }

  /** Is this word part of a known name, or a word marked "not a typo / not a name"? */
  knows(word: string): boolean {
    return this.knownLower.has(word.toLowerCase()) || this.ignored.has(word);
  }

  get empty(): boolean {
    return !this.exactRe && !this.looseRe;
  }

  kindOf(id: string): string {
    return this.kinds.get(id) ?? "other";
  }

  /** The entries a form (as written, without an ending) means, from both lists. */
  claimants(form: string): Owner[] {
    const owners = [...(this.exact.get(form) ?? [])];
    for (const o of this.loose.get(form.toLowerCase()) ?? []) if (!owners.some(([id]) => id === o[0])) owners.push(o);
    return owners;
  }

  /** The choice lines in a text: margin-note lines that start with a shared name and a colon. */
  choices(text: string, offset = 0): Choice[] {
    const out: Choice[] = [];
    CHOICE.lastIndex = 0;
    for (let m = CHOICE.exec(text); m; m = CHOICE.exec(text)) {
      const owners = this.claimants(m[1]).map(([id]) => id);
      if (owners.length < 2) continue;
      const words = m[2].split(",").map((w) => w.trim()).filter(Boolean);
      const at = { start: m.index + offset, end: m.index + m[0].length + offset, key: m[1].toLowerCase(), owners };
      if (words.length === 1 && words[0] === "?") {
        out.push({ ...at, ids: null });
        continue;
      }
      let chosen: string[] = [];
      for (const w of words) {
        const lw = w.toLowerCase();
        let match = owners.filter((o) => this.names.get(o)!.toLowerCase() === lw);
        if (!match.length) match = owners.filter((o) => (this.names.get(o)!.match(WORD) ?? []).some((x) => x.toLowerCase() === lw));
        if (match.length !== 1) {
          chosen = [];
          break;
        }
        if (!chosen.includes(match[0])) chosen.push(match[0]);
      }
      out.push({ ...at, ids: chosen });
    }
    return out;
  }

  /** Settle shared names by the choice lines before them (positions in the same document). */
  resolve(hits: Hit[], choices: Choice[]): Hit[] {
    if (!hits.some((h) => h.shared)) return hits;
    const settled = choices.filter((c) => c.ids === null || c.ids.length).sort((a, b) => a.end - b.end);
    return hits.map((h) => {
      if (!h.shared) return h;
      let choice: Choice | undefined;
      for (const c of settled) {
        if (c.end > h.start) break;
        if (c.key === h.shared.key) choice = c;
      }
      const ids = choice?.ids?.filter((id) => h.shared!.ids.includes(id)) ?? [];
      if (!ids.length) return h.kind === "ambiguous" && !h.chosen ? h : { ...h, kind: "ambiguous", entityId: h.shared.ids[0], chosen: undefined };
      return { ...h, kind: "alias", entityId: ids[0], entityKind: this.kindOf(ids[0]), chosen: ids };
    });
  }

  /** The mentions in a whole stored text, exactly as the server stores them: a chapter without its margin notes and a
   * journal entry without its choice lines, both following their choice lines; anything else as it is. */
  scanSource(text: string, source: string, nearMisses = true): Hit[] {
    if (source !== "chapter" && source !== "journal") return this.scan(text, 0, nearMisses);
    const choices = this.choices(text);
    const blank = (s: string) => " ".repeat(s.length);
    const story = source === "chapter"
      ? text.replace(MARGIN, blank)
      : choices.reduce((t, c) => t.slice(0, c.start) + blank(t.slice(c.start, c.end)) + t.slice(c.end), text);
    return this.resolve(this.scan(story, 0, nearMisses), choices);
  }

  /** Names (and likely misspellings) in `text`; `offset` is added to every position. A shared name comes back
   * ambiguous, with its claimants; `resolve` settles it by the choice lines. */
  scan(text: string, offset = 0, nearMisses = true): Hit[] {
    const raw: [number, number, Owner[], string, string][] = [];
    for (const [re, table, lower] of [[this.exactRe, this.exact, false], [this.looseRe, this.loose, true]] as const) {
      if (!re) continue;
      re.lastIndex = 0;
      for (let m = re.exec(text); m; m = re.exec(text)) {
        const owners = table.get(lower ? m[1].toLowerCase() : m[1]);
        if (owners) raw.push([m.index, m.index + m[0].length, owners, m[0], m[1]]);
      }
    }
    // overlapping matches: the longer one wins; the same span in both lists: everyone claiming it
    raw.sort((a, b) => a[0] - b[0] || b[1] - b[0] - (a[1] - a[0]));
    const spans: [number, number, Owner[], string, string][] = [];
    const taken: [number, number][] = [];
    const lowerText = text.toLowerCase();
    const excludedSpans = new Map<string, [number, number][]>();
    const excluded = (id: string, start: number, end: number) => {
      const phrases = this.exclusions.get(id);
      if (!phrases) return false;
      let spans = excludedSpans.get(id);
      if (!spans) {
        spans = [];
        for (const ph of phrases) for (let i = lowerText.indexOf(ph); i >= 0; i = lowerText.indexOf(ph, i + 1)) spans.push([i, i + ph.length]);
        excludedSpans.set(id, spans);
      }
      return spans.some(([s, e]) => s <= start && end <= e);
    };
    for (const [start, end, all, matched, key] of raw) {
      const owners = all.filter(([id]) => !excluded(id, start, end));
      if (!owners.length) continue;
      const last = spans[spans.length - 1];
      if (last && last[0] === start && last[1] === end) {
        for (const o of owners) if (!last[2].some(([id]) => id === o[0])) last[2].push(o);
        continue;
      }
      if (taken.length && start < taken[taken.length - 1][1]) continue;
      taken.push([start, end]);
      spans.push([start, end, [...owners], matched, key]);
    }
    const out: Hit[] = [];
    for (const [start, end, owners, matched, key] of spans) {
      const [id, kind] = owners[0];
      if (owners.length === 1) {
        out.push({ start: start + offset, end: end + offset, entityId: id, kind, entityKind: this.kindOf(id), matched });
        continue;
      }
      const ids = owners.map(([o]) => o);
      const kinds = new Set(ids.map((o) => this.kindOf(o)));
      out.push({
        start: start + offset, end: end + offset, entityId: id, kind: "ambiguous",
        entityKind: kinds.size === 1 ? this.kindOf(id) : "name", matched, shared: { key: key.toLowerCase(), ids, form: key },
      });
    }
    if (nearMisses && this.uses.size) {
      WORD.lastIndex = 0;
      for (let m = WORD.exec(text); m; m = WORD.exec(text)) {
        const word = m[0];
        const at = m.index;
        if (word[0] === word[0].toLowerCase() || taken.some(([s, e]) => s <= at && at < e)) continue;
        const base = word.replace(POSSESSIVE, "");
        if (base.length < NEAR_MIN || this.ignored.has(base) || this.ignored.has(word)) continue;
        if (this.knownLower.has(base.toLowerCase())) continue;
        const id = this.nearMiss(text, at, at + base.length);
        if (id) {
          out.push({ start: at + offset, end: at + base.length + offset, entityId: id, kind: "near_miss", entityKind: this.kindOf(id), matched: base });
        }
      }
    }
    return out.sort((a, b) => a.start - b.start);
  }
}
