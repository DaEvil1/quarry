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
  const d: number[][] = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    let rowMin = Infinity;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
      rowMin = Math.min(rowMin, d[i][j]);
    }
    if (rowMin > limit) return limit + 1;
  }
  return d[a.length][b.length];
}

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
        const limit = base.length <= 6 ? 1 : 2;
        let best: string | null = null;
        let bestD = limit + 1;
        for (const cand of this.owner.keys()) {
          const d = osa(base, cand, limit);
          if (d < bestD) {
            bestD = d;
            best = cand;
          }
        }
        if (best) {
          const id = this.owner.get(best)!;
          out.push({ start: at + offset, end: at + base.length + offset, entityId: id, kind: "near_miss", entityKind: this.kindOf(id), matched: base });
        }
      }
    }
    return out.sort((a, b) => a.start - b.start);
  }
}
