// Finding the world's names in text, in the browser, exactly as the server does (backend/src/quarry/mentions.py):
// names and other names on word boundaries with plural and possessive endings; capitals optional per entry; a
// character's first name (computed by the server); "not in this sense" phrases; and capitalised words one edit
// away from a name (two for long words, a swapped pair counting as one) as likely misspellings.

import type { Card } from "./cards";

export interface Hit {
  start: number;
  end: number;
  entityId: string;
  /** exact | alias | near_miss */
  kind: "exact" | "alias" | "near_miss";
  /** the entry's kind (character, place, …) */
  entityKind: string;
  matched: string;
}

const SUFFIX = "(?:'s|’s|s)?";
const WORD = /(?<![\p{L}\p{N}_'’-])\p{L}[\p{L}\p{N}]*(?:['’-][\p{L}\p{N}]+)*/gu;
const POSSESSIVE = /(?:'s|’s)$/;
const NEAR_MIN = 5;
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

/** How many lines' results a matcher remembers (a long chapter has a few hundred paragraphs). */
const LINE_CACHE = 4000;

export class Matcher {
  private exact = new Map<string, [string, Hit["kind"]]>();
  private loose = new Map<string, [string, Hit["kind"]]>();
  private exactRe: RegExp | null;
  private looseRe: RegExp | null;
  private exclusions = new Map<string, string[]>();
  private kinds = new Map<string, string>();
  private knownLower = new Set<string>();
  private owner = new Map<string, string>();
  private ignored: Set<string>;
  /** the near-miss candidates by length, so a word is only compared with names it could be one or two edits from */
  private ownersByLength = new Map<number, string[]>();
  /** ties go to the name met first, as on the server */
  private ownerOrder = new Map<string, number>();
  /** a word's verdict: the name it is likely a misspelling of, or null */
  private nearCache = new Map<string, string | null>();
  /** a line's hits (at offset 0), so typing in one paragraph doesn't rescan the others */
  private lineCache = new Map<string, Hit[]>();

  constructor(cards: Card[], ignored: Iterable<string> = []) {
    for (const c of cards) {
      this.kinds.set(c.id, c.kind);
      const forms: [string, Hit["kind"]][] = [[c.name, "exact"], ...c.aliases.map((a) => [a, "alias"] as [string, Hit["kind"]])];
      if (c.first_name) forms.push([c.first_name, "alias"]);
      for (const [raw, kind] of forms) {
        const f = raw.trim();
        if (!f) continue;
        if (c.match_case) {
          if (!this.exact.has(f)) this.exact.set(f, [c.id, kind]);
        } else if (!this.loose.has(f.toLowerCase())) this.loose.set(f.toLowerCase(), [c.id, kind]);
      }
      const ex = c.exclusions.map((x) => x.toLowerCase()).filter(Boolean);
      if (ex.length) this.exclusions.set(c.id, ex);
    }
    const alternation = (forms: Iterable<string>, flags: string) => {
      const list = [...forms].sort((a, b) => b.length - a.length);
      return list.length
        ? new RegExp(`(?<![\\p{L}\\p{N}_'’-])(${list.map(escape).join("|")})${SUFFIX}(?![\\p{L}\\p{N}_])`, flags)
        : null;
    };
    this.exactRe = alternation(this.exact.keys(), "gu");
    this.looseRe = alternation(this.loose.keys(), "giu");
    for (const [f, [id]] of [...this.exact, ...this.loose]) {
      for (const w of f.match(WORD) ?? []) {
        this.knownLower.add(w.toLowerCase());
        if (w.length >= NEAR_MIN) {
          const key = this.exact.has(f) ? w : w[0].toUpperCase() + w.slice(1);
          if (!this.owner.has(key)) this.owner.set(key, id);
        }
      }
    }
    this.ignored = new Set(ignored);
    let i = 0;
    for (const k of this.owner.keys()) {
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

  /** The name `base` is likely a misspelling of, if any. */
  private nearest(base: string): string | null {
    const known = this.nearCache.get(base);
    if (known !== undefined) return known;
    const limit = base.length <= 6 ? 1 : 2;
    let best: string | null = null;
    let bestD = limit + 1;
    for (let len = base.length - limit; len <= base.length + limit; len++) {
      for (const cand of this.ownersByLength.get(len) ?? []) {
        const d = osa(base, cand, Math.min(limit, bestD));
        if (d < bestD || (d === bestD && best !== null && this.ownerOrder.get(cand)! < this.ownerOrder.get(best)!)) {
          bestD = d;
          best = cand;
        }
      }
    }
    if (this.nearCache.size > 20_000) this.nearCache.clear();
    this.nearCache.set(base, best);
    return best;
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

  /** Names (and likely misspellings) in `text`; `offset` is added to every position. */
  scan(text: string, offset = 0, nearMisses = true): Hit[] {
    const raw: [number, number, string, Hit["kind"], string][] = [];
    for (const [re, table, lower] of [[this.exactRe, this.exact, false], [this.looseRe, this.loose, true]] as const) {
      if (!re) continue;
      re.lastIndex = 0;
      for (let m = re.exec(text); m; m = re.exec(text)) {
        const hit = table.get(lower ? m[1].toLowerCase() : m[1]);
        if (hit) raw.push([m.index, m.index + m[0].length, hit[0], hit[1], m[0]]);
      }
    }
    // overlapping matches: the longer one wins
    raw.sort((a, b) => a[0] - b[0] || b[1] - b[0] - (a[1] - a[0]));
    const out: Hit[] = [];
    const taken: [number, number][] = [];
    const lowerText = text.toLowerCase();
    const excludedSpans = new Map<string, [number, number][]>();
    for (const [start, end, id, kind, matched] of raw) {
      if (taken.length && start < taken[taken.length - 1][1]) continue;
      const phrases = this.exclusions.get(id);
      if (phrases) {
        let spans = excludedSpans.get(id);
        if (!spans) {
          spans = [];
          for (const ph of phrases) for (let i = lowerText.indexOf(ph); i >= 0; i = lowerText.indexOf(ph, i + 1)) spans.push([i, i + ph.length]);
          excludedSpans.set(id, spans);
        }
        if (spans.some(([s, e]) => s <= start && end <= e)) continue;
      }
      taken.push([start, end]);
      out.push({ start: start + offset, end: end + offset, entityId: id, kind, entityKind: this.kindOf(id), matched });
    }
    if (nearMisses && this.owner.size) {
      WORD.lastIndex = 0;
      for (let m = WORD.exec(text); m; m = WORD.exec(text)) {
        const word = m[0];
        const at = m.index;
        if (word[0] === word[0].toLowerCase() || taken.some(([s, e]) => s <= at && at < e)) continue;
        const base = word.replace(POSSESSIVE, "");
        if (base.length < NEAR_MIN || this.ignored.has(base) || this.ignored.has(word)) continue;
        if (this.knownLower.has(base.toLowerCase())) continue;
        const best = this.nearest(base);
        if (best) {
          const id = this.owner.get(best)!;
          out.push({ start: at + offset, end: at + base.length + offset, entityId: id, kind: "near_miss", entityKind: this.kindOf(id), matched: base });
        }
      }
    }
    return out.sort((a, b) => a.start - b.start);
  }
}
