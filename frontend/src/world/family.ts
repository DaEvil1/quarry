// The family tree (docs/SPEC.md §12.2): parenthood, marriage and recorded siblings read from the relationships the
// graph already loads, the way the place tree reads "inside" (so renamed or added types still count), kin worked out
// from them (siblings, grandparents, cousins, in-laws, step-relations), the words for each by the relative's gender
// field, and a layout in generations. "Ancestor of" (docs/SPEC.md §13.5) is a lineage whose generations between aren't
// recorded: drawn as a long dashed link, with only ancestors and descendants worked out across it. Everything here is
// worked out when shown, never stored.

import type { Gender } from "../types";
import type { GraphData } from "./graph";
import { holds, type IndexOf } from "./time";

export type LinkKind = "parent" | "married" | "sibling" | "ancestor";

/** One recorded family link: for "parent", `a` is the parent of `b`; for "ancestor", `a` is the ancestor of `b`. */
export interface FamilyLink {
  a: string;
  b: string;
  kind: LinkKind;
  /** the type's label as it reads from `a` (the parent, for parenthood) */
  label: string;
  /** how it reads from `b` */
  reverse: string;
  standing: string;
  /** a plain parent type ("parent of", "father of", "mother of"); any other ("adoptive parent of") shows its label */
  plain: boolean;
}

const PARENT = /(^|\s)(parent|father|mother) of$/i;
const CHILD = /(^|\s)(child|son|daughter) of$/i;
const PLAIN_PARENT = /^(parent|father|mother) of$/i;
const MARRIED = /^(married to|spouse of|husband of|wife of|wed to)$/i;
const SIBLING = /^(sibling|brother|sister) of$/i;
const ANCESTOR = /(^|\s)ancestor of$/i;
const DESCENDANT = /(^|\s)descendant of$/i;

const clean = (s: string | null | undefined) => (s ?? "").trim().replace(/\s+/g, " ");

/** How a character–character type reads as family: 1 "A parent of B", -1 "B parent of A", else married, sibling or
 * nothing. */
export function readType(label: string, reverse: string | null): { kind: LinkKind; dir: 1 | -1 } | null {
  const l = clean(label);
  const r = clean(reverse);
  if (PARENT.test(l) || CHILD.test(r)) return { kind: "parent", dir: 1 };
  if (CHILD.test(l) || PARENT.test(r)) return { kind: "parent", dir: -1 };
  if (ANCESTOR.test(l) || DESCENDANT.test(r)) return { kind: "ancestor", dir: 1 };
  if (DESCENDANT.test(l) || ANCESTOR.test(r)) return { kind: "ancestor", dir: -1 };
  if (MARRIED.test(l) || MARRIED.test(r)) return { kind: "married", dir: 1 };
  if (SIBLING.test(l) || SIBLING.test(r)) return { kind: "sibling", dir: 1 };
  return null;
}

export interface FamilyFilter {
  asOf: number | null;
  indexOf: IndexOf;
  standings: Set<string>;
}

/** The family links that hold (as of a chapter, with the standings shown), between characters. */
export function familyLinks(data: GraphData, f: FamilyFilter): FamilyLink[] {
  const kind = new Map(data.nodes.map((n) => [n.id, n.kind]));
  const out: FamilyLink[] = [];
  for (const e of data.edges) {
    if (kind.get(e.a) !== "character" || kind.get(e.b) !== "character" || e.a === e.b) continue;
    if (!f.standings.has(e.standing)) continue;
    if (f.asOf !== null && !holds(e, f.asOf, f.indexOf)) continue;
    const t = readType(e.label, e.reverse_label);
    if (!t) continue;
    const reverse = clean(e.reverse_label) || clean(e.label);
    if (t.kind === "ancestor") {
      // "descendant of" (or a reverse "ancestor of"): B is the ancestor
      const [a, b] = t.dir === 1 ? [e.a, e.b] : [e.b, e.a];
      out.push({ a, b, kind: "ancestor", label: t.dir === 1 ? clean(e.label) : reverse, reverse: t.dir === 1 ? reverse : clean(e.label), standing: e.standing, plain: true });
    } else if (t.kind === "parent" && t.dir === -1) {
      // "son of" / "father of": B is the parent
      out.push({ a: e.b, b: e.a, kind: "parent", label: reverse, reverse: clean(e.label), standing: e.standing, plain: PLAIN_PARENT.test(reverse) });
    } else {
      out.push({ a: e.a, b: e.b, kind: t.kind, label: clean(e.label), reverse, standing: e.standing, plain: t.kind !== "parent" || PLAIN_PARENT.test(clean(e.label)) });
    }
  }
  return out;
}

export class Family {
  parents = new Map<string, Set<string>>();
  children = new Map<string, Set<string>>();
  spouses = new Map<string, Set<string>>();
  siblings = new Map<string, Set<string>>();
  /** recorded lineages: descendant -> ancestors, and ancestor -> descendants */
  ancestors = new Map<string, Set<string>>();
  descendants = new Map<string, Set<string>>();
  people = new Set<string>();

  constructor(public links: FamilyLink[]) {
    const add = (m: Map<string, Set<string>>, x: string, y: string) => {
      if (!m.has(x)) m.set(x, new Set());
      m.get(x)!.add(y);
    };
    for (const l of links) {
      this.people.add(l.a).add(l.b);
      if (l.kind === "parent") (add(this.parents, l.b, l.a), add(this.children, l.a, l.b));
      else if (l.kind === "ancestor") (add(this.ancestors, l.b, l.a), add(this.descendants, l.a, l.b));
      else if (l.kind === "married") (add(this.spouses, l.a, l.b), add(this.spouses, l.b, l.a));
      else (add(this.siblings, l.a, l.b), add(this.siblings, l.b, l.a));
    }
  }

  get = (m: Map<string, Set<string>>, x: string): Set<string> => m.get(x) ?? new Set();

  /** Everyone connected to `id` through family links. */
  connected(id: string): Set<string> {
    const seen = new Set([id]);
    const todo = [id];
    while (todo.length) {
      const x = todo.pop()!;
      for (const m of [this.parents, this.children, this.spouses, this.siblings, this.ancestors, this.descendants]) {
        for (const y of this.get(m, x)) if (!seen.has(y)) (seen.add(y), todo.push(y));
      }
    }
    return seen;
  }

  /** Ancestors (up) or descendants (down) reached only by crossing a recorded "ancestor of": through parent links and
   * lineages, past at least one lineage. Those are ancestors and descendants, with no generations counted. */
  lineage(id: string, up: boolean): Set<string> {
    const step = up ? this.parents : this.children;
    const far = up ? this.ancestors : this.descendants;
    // each person reached, and whether the way there crossed a lineage
    const crossed = new Map<string, boolean>([[id, false]]);
    const todo = [id];
    while (todo.length) {
      const x = todo.shift()!;
      const was = crossed.get(x)!;
      for (const [m, via] of [[step, was], [far, true]] as const) {
        for (const y of this.get(m, x)) {
          if (y === id) continue;
          const prev = crossed.get(y);
          // a way that doesn't cross a lineage wins (they are then counted in generations)
          if (prev === undefined || (prev && !via)) {
            crossed.set(y, via);
            todo.push(y);
          }
        }
      }
    }
    return new Set([...crossed].filter(([y, c]) => c && y !== id).map(([y]) => y));
  }

  /** Siblings: recorded, or sharing any parent. */
  siblingsOf(id: string): Set<string> {
    const out = new Set(this.get(this.siblings, id));
    for (const p of this.get(this.parents, id)) for (const c of this.get(this.children, p)) if (c !== id) out.add(c);
    out.delete(id);
    return out;
  }

  /** Ancestors (up) or descendants (down) with how many generations away (1 is a parent or child). */
  generations(id: string, up: boolean): Map<string, number> {
    const m = up ? this.parents : this.children;
    const out = new Map<string, number>();
    let frontier = [id];
    for (let d = 1; frontier.length && d < 50; d++) {
      const next: string[] = [];
      for (const x of frontier) for (const y of this.get(m, x)) if (y !== id && !out.has(y)) (out.set(y, d), next.push(y));
      frontier = next;
    }
    return out;
  }

  /** People recorded as their own ancestor: each loop once, as the names' ids in order (A → B → … → A). */
  loops(): string[][] {
    const out: string[][] = [];
    const seen = new Set<string>();
    for (const start of [...this.people].sort()) {
      const stack: [string, string[]][] = [[start, [start]]];
      const visited = new Set<string>();
      while (stack.length) {
        const [node, path] = stack.pop()!;
        for (const up of [...this.get(this.parents, node), ...this.get(this.ancestors, node)]) {
          if (up === start) {
            const key = [...path].sort().join("|");
            if (!seen.has(key)) (seen.add(key), out.push([start, ...path.slice(1).reverse(), start]));
          } else if (!visited.has(up)) {
            visited.add(up);
            stack.push([up, [...path, up]]);
          }
        }
      }
    }
    return out;
  }
}

// ---- kin -------------------------------------------------------------------------------------------------------

export type Relation =
  | "parent"
  | "child"
  | "spouse"
  | "sibling"
  | "half-sibling"
  | "grandparent"
  | "grandchild"
  | "ancestor"
  | "descendant"
  | "parent's sibling"
  | "sibling's child"
  | "cousin"
  | "relative"
  | "parent-in-law"
  | "child-in-law"
  | "sibling-in-law"
  | "step-parent"
  | "stepchild";

export interface Kin {
  id: string;
  relation: Relation;
  /** for grandparent / grandchild: how many "great-" */
  greats: number;
  /** recorded (a relationship says so) or worked out */
  recorded: boolean;
  /** for a recorded link: its label as it reads from the relative ("adoptive parent of"), and whether it is a plain
   * parent, marriage or sibling type (then it gets the kin word, like one worked out) */
  label?: string;
  plain?: boolean;
  /** the people in between, from the centre's side */
  via: string[];
}

const WORDS: Record<Relation, [string, string, string]> = {
  // female, male, general
  parent: ["mother", "father", "parent"],
  child: ["daughter", "son", "child"],
  spouse: ["wife", "husband", "spouse"],
  sibling: ["sister", "brother", "sibling"],
  "half-sibling": ["half-sister", "half-brother", "half-sibling"],
  grandparent: ["grandmother", "grandfather", "grandparent"],
  grandchild: ["granddaughter", "grandson", "grandchild"],
  ancestor: ["ancestor", "ancestor", "ancestor"],
  descendant: ["descendant", "descendant", "descendant"],
  "parent's sibling": ["aunt", "uncle", "parent's sibling"],
  "sibling's child": ["niece", "nephew", "sibling's child"],
  cousin: ["cousin", "cousin", "cousin"],
  relative: ["relative", "relative", "relative"],
  "parent-in-law": ["mother-in-law", "father-in-law", "parent-in-law"],
  "child-in-law": ["daughter-in-law", "son-in-law", "child-in-law"],
  "sibling-in-law": ["sister-in-law", "brother-in-law", "sibling-in-law"],
  "step-parent": ["stepmother", "stepfather", "step-parent"],
  stepchild: ["stepdaughter", "stepson", "stepchild"],
};

/** The word for a relation, by the relative's gender: nonbinary and not set give the general word. */
export function kinWord(relation: Relation, gender: Gender | null | undefined, greats = 0): string {
  const w = WORDS[relation][gender === "female" ? 0 : gender === "male" ? 1 : 2];
  return "great-".repeat(greats) + w;
}

/** How many "great-" a grand- word takes at most; further generations are ancestor or descendant. */
export const MAX_GREATS = 4;

/** Everyone related to `centre`, recorded and worked out, each with how. Two people related in two ways have two
 * entries; a recorded relationship wins over the same relation worked out. */
export function kinOf(fam: Family, centre: string): Kin[] {
  const out: Kin[] = [];
  const has = new Map<string, Set<Relation>>();
  const put = (k: Kin) => {
    if (k.id === centre) return;
    const got = has.get(k.id) ?? new Set();
    // a recorded sibling isn't worked out again as a sibling (or a half-sibling)
    if (got.has(k.relation) || (k.relation === "half-sibling" && got.has("sibling"))) return;
    got.add(k.relation);
    has.set(k.id, got);
    out.push(k);
  };
  const via = (to: string) => pathBetween(fam, centre, to);
  const P = fam.get(fam.parents, centre);
  const C = fam.get(fam.children, centre);
  const S = fam.get(fam.spouses, centre);

  // recorded
  for (const l of fam.links) {
    if (l.kind === "parent" && l.b === centre) put({ id: l.a, relation: "parent", greats: 0, recorded: true, label: l.label, plain: l.plain, via: [] });
    if (l.kind === "parent" && l.a === centre) put({ id: l.b, relation: "child", greats: 0, recorded: true, label: l.reverse, plain: l.plain, via: [] });
    if (l.kind === "married" && (l.a === centre || l.b === centre)) {
      put({ id: l.a === centre ? l.b : l.a, relation: "spouse", greats: 0, recorded: true, label: l.a === centre ? l.reverse : l.label, plain: true, via: [] });
    }
    if (l.kind === "sibling" && (l.a === centre || l.b === centre)) {
      put({ id: l.a === centre ? l.b : l.a, relation: "sibling", greats: 0, recorded: true, label: l.a === centre ? l.reverse : l.label, plain: true, via: [] });
    }
    if (l.kind === "ancestor" && l.b === centre) put({ id: l.a, relation: "ancestor", greats: 0, recorded: true, label: l.label, plain: true, via: [] });
    if (l.kind === "ancestor" && l.a === centre) put({ id: l.b, relation: "descendant", greats: 0, recorded: true, label: l.reverse, plain: true, via: [] });
  }

  // worked out: siblings by a shared parent (half when each has a parent the other doesn't)
  const sibs = fam.siblingsOf(centre);
  for (const s of sibs) {
    if (fam.get(fam.siblings, centre).has(s)) continue;
    const theirs = fam.get(fam.parents, s);
    const half = [...theirs].some((p) => !P.has(p)) && [...P].some((p) => !theirs.has(p));
    put({ id: s, relation: half ? "half-sibling" : "sibling", greats: 0, recorded: false, via: via(s) });
  }
  // up and down the generations
  for (const [up, relation, far] of [[true, "grandparent", "ancestor"], [false, "grandchild", "descendant"]] as const) {
    for (const [id, d] of fam.generations(centre, up)) {
      if (d < 2) continue;
      const greats = d - 2;
      put(greats <= MAX_GREATS ? { id, relation, greats, recorded: false, via: via(id) } : { id, relation: far, greats: 0, recorded: false, via: via(id) });
    }
  }
  // across a recorded lineage: ancestors and descendants only (no cousins, siblings or in-laws through it)
  for (const id of fam.lineage(centre, true)) put({ id, relation: "ancestor", greats: 0, recorded: false, via: via(id) });
  for (const id of fam.lineage(centre, false)) put({ id, relation: "descendant", greats: 0, recorded: false, via: via(id) });
  // parents' siblings, siblings' children, cousins
  for (const p of P) {
    for (const ps of fam.siblingsOf(p)) {
      if (!P.has(ps)) put({ id: ps, relation: "parent's sibling", greats: 0, recorded: false, via: via(ps) });
      for (const c of fam.get(fam.children, ps)) if (c !== centre && !sibs.has(c)) put({ id: c, relation: "cousin", greats: 0, recorded: false, via: via(c) });
    }
  }
  for (const s of sibs) for (const c of fam.get(fam.children, s)) if (!C.has(c)) put({ id: c, relation: "sibling's child", greats: 0, recorded: false, via: via(c) });
  // by marriage
  for (const sp of S) {
    for (const p of fam.get(fam.parents, sp)) if (!P.has(p)) put({ id: p, relation: "parent-in-law", greats: 0, recorded: false, via: via(p) });
    for (const s of fam.siblingsOf(sp)) put({ id: s, relation: "sibling-in-law", greats: 0, recorded: false, via: via(s) });
    for (const c of fam.get(fam.children, sp)) if (!C.has(c)) put({ id: c, relation: "stepchild", greats: 0, recorded: false, via: via(c) });
  }
  for (const c of C) for (const cs of fam.get(fam.spouses, c)) put({ id: cs, relation: "child-in-law", greats: 0, recorded: false, via: via(cs) });
  for (const s of sibs) for (const ss of fam.get(fam.spouses, s)) if (ss !== centre) put({ id: ss, relation: "sibling-in-law", greats: 0, recorded: false, via: via(ss) });
  for (const p of P) for (const ps of fam.get(fam.spouses, p)) if (!P.has(ps)) put({ id: ps, relation: "step-parent", greats: 0, recorded: false, via: via(ps) });
  // any other blood relative: a shared ancestor
  const mine = new Set([centre, ...fam.generations(centre, true).keys()]);
  const blood: Relation[] = ["parent", "child", "sibling", "half-sibling", "grandparent", "grandchild", "ancestor", "descendant", "parent's sibling", "sibling's child", "cousin"];
  for (const id of fam.connected(centre)) {
    if (id === centre || [...(has.get(id) ?? [])].some((r) => blood.includes(r))) continue;
    const theirs = new Set([id, ...fam.generations(id, true).keys()]);
    if ([...theirs].some((x) => mine.has(x))) put({ id, relation: "relative", greats: 0, recorded: false, via: via(id) });
  }
  return out;
}

/** The people between two in the family (shortest way through any family link), not counting either end. */
export function pathBetween(fam: Family, from: string, to: string): string[] {
  const prev = new Map<string, string>([[from, ""]]);
  const queue = [from];
  while (queue.length) {
    const x = queue.shift()!;
    if (x === to) break;
    for (const m of [fam.parents, fam.children, fam.spouses, fam.siblings, fam.ancestors, fam.descendants]) {
      for (const y of [...fam.get(m, x)].sort()) if (!prev.has(y)) (prev.set(y, x), queue.push(y));
    }
  }
  if (!prev.has(to)) return [];
  const path: string[] = [];
  for (let x = prev.get(to)!; x && x !== from; x = prev.get(x)!) path.unshift(x);
  return path;
}

/** "granddaughter", "great-uncle" … for a kin entry; a recorded link of another type than the plain ones keeps its
 * own label ("adoptive parent of"). */
export function kinText(k: Kin, gender: Gender | null | undefined): string {
  return k.recorded && k.label && !k.plain ? k.label : kinWord(k.relation, gender, k.greats);
}

// ---- the drawing --------------------------------------------------------------------------------------------------

export interface TreePerson {
  id: string;
  x: number;
  y: number;
  gen: number;
}

export interface TreeLine {
  /** a couple: married (double) or both parents of a child (single); a child's line down from its parents; the
   * small "?" over siblings with no recorded parent; a long dashed line down from a recorded ancestor */
  kind: "married" | "coparents" | "child" | "unknown" | "ancestor";
  points: [number, number][];
  dashed: boolean;
  /** the parent type's label, for one other than the plain one */
  label?: string;
}

export interface Tree {
  people: TreePerson[];
  lines: TreeLine[];
  unknown: { x: number; y: number }[];
  width: number;
  height: number;
}

export const SLOT = 150;
export const ROW = 110;
/** room above the first generation, for a "?" over siblings without a recorded parent */
const TOP = 80;

/**
 * Lay out everyone connected to `centre`: generations top to bottom (parents above children, a couple and siblings
 * on one row), then a few sweeps that keep couples side by side and children under their parents. Laid out once.
 */
export function layoutTree(fam: Family, centre: string, order: (id: string) => string = (id) => id, gap: (ancestor: string, descendant: string) => string = () => "generations not recorded"): Tree {
  const people = fam.connected(centre);
  // generations, from the centre outward
  const gen = new Map<string, number>([[centre, 0]]);
  const queue = [centre];
  while (queue.length) {
    const x = queue.shift()!;
    const g = gen.get(x)!;
    const step = (m: Map<string, Set<string>>, d: number) => {
      for (const y of fam.get(m, x)) if (people.has(y) && !gen.has(y)) (gen.set(y, g + d), queue.push(y));
    };
    step(fam.parents, -1);
    step(fam.children, 1);
    step(fam.spouses, 0);
    step(fam.siblings, 0);
    // a recorded ancestor at least two rows above
    step(fam.ancestors, -2);
    step(fam.descendants, 2);
  }
  const top = Math.min(...gen.values());
  const rows = new Map<number, string[]>();
  for (const id of [...people].sort((a, b) => order(a).localeCompare(order(b)))) {
    const g = gen.get(id)! - top;
    rows.set(g, [...(rows.get(g) ?? []), id]);
  }
  const depth = Math.max(...rows.keys()) + 1;
  // within a row, partners side by side: each row is a list of units (a person and the partners chained to them)
  const partners = (id: string) => {
    const out = new Set(fam.get(fam.spouses, id));
    // both recorded parents of a child, not married: a couple too
    for (const c of fam.get(fam.children, id)) for (const p of fam.get(fam.parents, c)) if (p !== id) out.add(p);
    return out;
  };
  const units = new Map<number, string[][]>();
  for (const [g, ids] of rows) {
    const placed = new Set<string>();
    const list: string[][] = [];
    for (const id of ids) {
      if (placed.has(id)) continue;
      const unit: string[] = [];
      const grow = (x: string) => {
        if (placed.has(x) || !ids.includes(x)) return;
        placed.add(x);
        unit.push(x);
        for (const p of [...partners(x)].sort((a, b) => order(a).localeCompare(order(b)))) grow(p);
      };
      grow(id);
      list.push(unit);
    }
    units.set(g, list);
  }
  const x = new Map<string, number>();
  const place = () => {
    for (const [, list] of units) {
      let at = 0;
      for (const unit of list) for (const id of unit) x.set(id, at++);
    }
  };
  place();
  const avg = (xs: number[]) => xs.reduce((s, v) => s + v, 0) / xs.length;
  const key = (unit: string[], m: Map<string, Set<string>>) => {
    const xs = unit.flatMap((id) => [...fam.get(m, id)].filter((y) => x.has(y)).map((y) => x.get(y)!));
    return xs.length ? avg(xs) : null;
  };
  for (let sweep = 0; sweep < 4; sweep++) {
    const down = sweep % 2 === 0;
    const gens = [...units.keys()].sort((a, b) => (down ? a - b : b - a));
    for (const g of gens) {
      const list = units.get(g)!;
      const keyed = list.map((u, i) => ({ u, k: key(u, down ? fam.parents : fam.children) ?? (u.length ? x.get(u[0]!)! : i) }));
      keyed.sort((a, b) => a.k - b.k);
      units.set(g, keyed.map((k) => k.u));
      let at = 0;
      for (const { u } of keyed) for (const id of u) x.set(id, at++);
    }
  }
  // where each one goes across: a unit's people a slot apart, pulled under its parents (and over its children) as far
  // as the order and the room allow; the last pull is downward, so children end up under their parents
  const at = new Map<string, number>([...x].map(([id, slot]) => [id, slot * SLOT]));
  const pull = (m: Map<string, Set<string>>, gens: number[]) => {
    for (const g of gens) {
      let end = -Infinity;
      for (const u of units.get(g)!) {
        const xs = u.flatMap((id) => [...fam.get(m, id)].filter((y) => at.has(y)).map((y) => at.get(y)!));
        const want = xs.length ? avg(xs) - ((u.length - 1) * SLOT) / 2 : at.get(u[0]!)!;
        const start = Math.max(want, end + SLOT);
        u.forEach((id, i) => at.set(id, start + i * SLOT));
        end = start + (u.length - 1) * SLOT;
      }
    }
  };
  const down = [...units.keys()].sort((a, b) => a - b);
  for (let pass = 0; pass < 3; pass++) {
    pull(fam.children, [...down].reverse());
    pull(fam.parents, down);
  }
  const left = Math.min(...at.values());
  const out: TreePerson[] = [];
  const pos = new Map<string, { x: number; y: number }>();
  for (const [g, list] of units) {
    for (const u of list) {
      for (const id of u) {
        const p = { x: at.get(id)! - left + SLOT / 2, y: g * ROW + TOP };
        pos.set(id, p);
        out.push({ id, ...p, gen: g });
      }
    }
  }
  const widest = (Math.max(...at.values()) - left) / SLOT + 1;
  // lines
  const lines: TreeLine[] = [];
  const dashed = (l: FamilyLink) => l.standing !== "canon";
  const linkOf = (a: string, b: string, kind: LinkKind) => fam.links.find((l) => l.kind === kind && ((l.a === a && l.b === b) || (l.a === b && l.b === a)));
  const coupleDone = new Set<string>();
  for (const l of fam.links) {
    if (l.kind !== "married") continue;
    const a = pos.get(l.a);
    const b = pos.get(l.b);
    if (!a || !b) continue;
    coupleDone.add([l.a, l.b].sort().join("|"));
    lines.push({ kind: "married", points: [[a.x, a.y], [b.x, b.y]], dashed: dashed(l) });
  }
  // children hang from their parents (from the pair's middle, or from the one parent recorded)
  const byParents = new Map<string, string[]>();
  for (const id of people) {
    const ps = [...fam.get(fam.parents, id)].filter((p) => pos.has(p)).sort();
    if (!ps.length) continue;
    const k = ps.join("|");
    byParents.set(k, [...(byParents.get(k) ?? []), id]);
  }
  const unknown: { x: number; y: number }[] = [];
  // a lineage: a long dashed line from the ancestor down to the descendant, labelled with the gap
  for (const l of fam.links) {
    if (l.kind !== "ancestor") continue;
    const a = pos.get(l.a);
    const d = pos.get(l.b);
    if (!a || !d) continue;
    const mid = (a.y + d.y) / 2;
    lines.push({ kind: "ancestor", points: [[a.x, a.y + 26], [a.x, mid], [d.x, mid], [d.x, d.y - 26]], dashed: true, label: gap(l.a, l.b) });
  }
  for (const [k, kids] of byParents) {
    const ps = k.split("|");
    if (ps.length >= 2) {
      for (let i = 0; i + 1 < ps.length; i++) {
        const pair = [ps[i]!, ps[i + 1]!].sort().join("|");
        if (!coupleDone.has(pair)) {
          coupleDone.add(pair);
          const a = pos.get(ps[i]!)!;
          const b = pos.get(ps[i + 1]!)!;
          lines.push({ kind: "coparents", points: [[a.x, a.y], [b.x, b.y]], dashed: false });
        }
      }
    }
    const from = { x: avg(ps.map((p) => pos.get(p)!.x)), y: avg(ps.map((p) => pos.get(p)!.y)) };
    for (const kid of kids) {
      const c = pos.get(kid)!;
      const mid = (from.y + c.y) / 2;
      const link = ps.map((p) => linkOf(p, kid, "parent")).find((l) => l && !l.plain) ?? linkOf(ps[0]!, kid, "parent");
      lines.push({ kind: "child", points: [[from.x, from.y + 14], [from.x, mid], [c.x, mid], [c.x, c.y - 26]], dashed: !!link && dashed(link), label: link && !link.plain ? link.label : undefined });
    }
  }
  // recorded siblings with no recorded parent hang together from a small "?"
  const orphans = new Map<string, string[]>();
  for (const id of people) {
    if (fam.get(fam.parents, id).size || !fam.get(fam.siblings, id).size) continue;
    const group = [id, ...fam.get(fam.siblings, id)].filter((s) => !fam.get(fam.parents, s).size).sort();
    orphans.set(group.join("|"), group);
  }
  for (const group of orphans.values()) {
    const ps = group.map((g) => pos.get(g)!).filter(Boolean);
    if (ps.length < 2) continue;
    const q = { x: avg(ps.map((p) => p.x)), y: ps[0]!.y - ROW / 2 - 10 };
    unknown.push(q);
    for (const p of ps) lines.push({ kind: "unknown", points: [[q.x, q.y + 8], [q.x, q.y + 22], [p.x, q.y + 22], [p.x, p.y - 26]], dashed: false });
  }
  return { people: out, lines, unknown, width: widest * SLOT, height: depth * ROW + TOP };
}
