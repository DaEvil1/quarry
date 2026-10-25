// The world as a graph (docs/WORLD-MODEL.md §6): which entries and links to show at a point in the story, who is
// within one or two steps of someone, clusters (groups more connected inside than out, by modularity), and the
// place tree. Pure functions; GraphView draws the result.

import type { EntityKind, Gender, Standing } from "../types";
import { atOrBefore, holds, type At, type IndexOf } from "./time";

export interface GraphData {
  /** with each entry's level (a project's slug, or null for the world) and a character's gender */
  nodes: { id: string; name: string; kind: EntityKind; summary: string; project?: string | null; gender?: Gender | null }[];
  edges: {
    id: string;
    a: string;
    b: string;
    type_id: string;
    label: string;
    reverse_label: string | null;
    standing: Standing;
    from_chapter_id: string | null;
    until_chapter_id: string | null;
    from_time?: number | null;
    from_approx?: boolean;
    until_time?: number | null;
    until_approx?: boolean;
    outside_time?: boolean;
  }[];
  types: { id: string; a_kind: string; b_kind: string; label: string; reverse_label: string | null }[];
  presence: { entity_id: string; place_id: string; chapter_id: string }[];
  cooccurrence: { a: string; b: string; by_chapter: Record<string, number> }[];
}

export interface Link {
  a: string;
  b: string;
  /** a recorded relationship, or co-occurrence (named in the same paragraph) */
  kind: "recorded" | "co";
  label: string;
  weight: number;
  standing?: Standing;
}

export interface Filters {
  /** a point on the clock (a chapter's place, or a time), or null for the whole story */
  asOf: At | null;
  indexOf: IndexOf;
  kinds: Set<string>;
  standings: Set<string>;
  /** relationship types to show; empty = all */
  typeIds: Set<string>;
  /** co-occurrence links: paragraphs needed (0 = off) */
  coMin: number;
}

/** The links visible with these filters. Co-occurrence counts the paragraphs up to the as-of chapter. */
export function visibleLinks(data: GraphData, f: Filters): Link[] {
  const kind = new Map(data.nodes.map((n) => [n.id, n.kind]));
  const shown = (id: string) => f.kinds.has(kind.get(id) ?? "other");
  const out: Link[] = [];
  for (const e of data.edges) {
    if (!shown(e.a) || !shown(e.b) || !f.standings.has(e.standing)) continue;
    if (f.typeIds.size && !f.typeIds.has(e.type_id)) continue;
    if (f.asOf !== null && !holds(e, f.asOf, f.indexOf)) continue;
    out.push({ a: e.a, b: e.b, kind: "recorded", label: e.label, weight: 3, standing: e.standing });
  }
  if (f.coMin > 0) {
    const recorded = new Set(out.map((l) => [l.a, l.b].sort().join("|")));
    for (const c of data.cooccurrence) {
      if (!shown(c.a) || !shown(c.b) || recorded.has([c.a, c.b].sort().join("|"))) continue;
      let n = 0;
      for (const [ch, k] of Object.entries(c.by_chapter)) {
        if (f.asOf === null || (f.indexOf(ch) !== undefined && atOrBefore(ch, f.asOf, f.indexOf))) n += k;
      }
      if (n >= f.coMin) out.push({ a: c.a, b: c.b, kind: "co", label: `named together in ${n} paragraph${n === 1 ? "" : "s"}`, weight: Math.min(2, n / f.coMin) });
    }
  }
  return out;
}

/** Steps from `centre` to everyone within `depth` (centre itself at 0). */
export function neighbourhood(links: Link[], centre: string, depth: number): Map<string, number> {
  const adj = new Map<string, string[]>();
  for (const l of links) {
    adj.set(l.a, [...(adj.get(l.a) ?? []), l.b]);
    adj.set(l.b, [...(adj.get(l.b) ?? []), l.a]);
  }
  const dist = new Map([[centre, 0]]);
  let frontier = [centre];
  for (let d = 1; d <= depth; d++) {
    const next: string[] = [];
    for (const x of frontier) for (const y of adj.get(x) ?? []) if (!dist.has(y)) (dist.set(y, d), next.push(y));
    frontier = next;
  }
  return dist;
}

/**
 * Clusters by modularity (Louvain): move each node to the neighbouring group that raises modularity most, until
 * nothing moves; then treat each group as one node and repeat. Deterministic (nodes in sorted order). Returns a
 * cluster number per node, 0 for the largest; nodes alone in a group get -1.
 */
export function clusters(nodeIds: string[], links: Link[]): Map<string, number> {
  // weighted adjacency between current super-nodes (self-loops hold weight inside a group)
  let adj = new Map<number, Map<number, number>>();
  const ids = [...nodeIds].sort();
  const index = new Map(ids.map((id, i) => [id, i]));
  for (let i = 0; i < ids.length; i++) adj.set(i, new Map());
  for (const l of links) {
    const a = index.get(l.a);
    const b = index.get(l.b);
    if (a === undefined || b === undefined || a === b) continue;
    adj.get(a)!.set(b, (adj.get(a)!.get(b) ?? 0) + l.weight);
    adj.get(b)!.set(a, (adj.get(b)!.get(a) ?? 0) + l.weight);
  }
  let membership = ids.map((_, i) => i); // original node -> super-node
  for (let level = 0; level < 10; level++) {
    const nodes = [...adj.keys()].sort((x, y) => x - y);
    const degree = new Map(nodes.map((n) => [n, [...adj.get(n)!].reduce((s, [m, w]) => s + (m === n ? 2 * w : w), 0)]));
    const m2 = [...degree.values()].reduce((s, k) => s + k, 0);
    if (m2 === 0) break;
    const comm = new Map(nodes.map((n) => [n, n]));
    const tot = new Map(nodes.map((n) => [n, degree.get(n)!]));
    let movedAny = false;
    for (let pass = 0; pass < 50; pass++) {
      let moved = false;
      for (const n of nodes) {
        const k = degree.get(n)!;
        const own = comm.get(n)!;
        tot.set(own, tot.get(own)! - k);
        const toComm = new Map<number, number>();
        for (const [m, w] of adj.get(n)!) if (m !== n) toComm.set(comm.get(m)!, (toComm.get(comm.get(m)!) ?? 0) + w);
        let best = own;
        let bestGain = (toComm.get(own) ?? 0) - (tot.get(own)! * k) / m2;
        for (const [c, w] of [...toComm].sort((x, y) => x[0] - y[0])) {
          const gain = w - (tot.get(c)! * k) / m2;
          if (gain > bestGain + 1e-9) (best = c), (bestGain = gain);
        }
        tot.set(best, tot.get(best)! + k);
        if (best !== own) {
          comm.set(n, best);
          moved = movedAny = true;
        }
      }
      if (!moved) break;
    }
    if (!movedAny) break;
    // aggregate: each group becomes one node
    const groups = [...new Set(nodes.map((n) => comm.get(n)!))].sort((x, y) => x - y);
    const renumber = new Map(groups.map((g, i) => [g, i]));
    const next = new Map<number, Map<number, number>>(groups.map((_, i) => [i, new Map()]));
    for (const n of nodes) {
      const cn = renumber.get(comm.get(n)!)!;
      for (const [m, w] of adj.get(n)!) {
        const cm = renumber.get(comm.get(m)!)!;
        // each edge is seen from both ends; a self-loop only once
        const add = m === n ? w : w / (cn === cm ? 2 : 1);
        next.get(cn)!.set(cm, (next.get(cn)!.get(cm) ?? 0) + add);
      }
    }
    membership = membership.map((s) => renumber.get(comm.get(s)!)!);
    adj = next;
  }
  // number groups by size, largest first; singletons are no cluster
  const size = new Map<number, number>();
  for (const s of membership) size.set(s, (size.get(s) ?? 0) + 1);
  const order = [...size].filter(([, n]) => n > 1).sort((x, y) => y[1] - x[1] || x[0] - y[0]).map(([s]) => s);
  const label = new Map(order.map((s, i) => [s, i]));
  return new Map(ids.map((id, i) => [id, label.get(membership[i]!) ?? -1]));
}

export interface PlaceNode {
  id: string;
  name: string;
  children: PlaceNode[];
  /** relationships to characters and others, read from the place ("home of": [Isolde]) */
  people: { label: string; who: { id: string; name: string; kind: string }[] }[];
  /** recorded "is at" in the as-of chapter */
  here: { id: string; name: string; kind: string }[];
}

/** Is this place–place type "A inside B"? (the starting vocabulary's inside / contains, or anything read that way) */
const isInside = (label: string, reverse: string | null) => /^(inside|in|part of|within)$/i.test(label) || /^contains$/i.test(reverse ?? "");

/** Places nested by inside/contains, each with who lives or works there and who is there as of a chapter. */
export function placeTree(data: GraphData, asOf: At | null, indexOf: IndexOf, chapterAt: string | null): PlaceNode[] {
  const node = new Map(data.nodes.map((n) => [n.id, n]));
  const places = data.nodes.filter((n) => n.kind === "place");
  const tree = new Map<string, PlaceNode>(places.map((p) => [p.id, { id: p.id, name: p.name, children: [], people: [], here: [] }]));
  const parent = new Map<string, string>();
  const holdsNow = (e: GraphData["edges"][number]) => asOf === null || holds(e, asOf, indexOf);
  for (const e of data.edges) {
    if (!holdsNow(e) || e.standing === "rumour") continue;
    const a = node.get(e.a);
    const b = node.get(e.b);
    if (!a || !b) continue;
    if (a.kind === "place" && b.kind === "place" && isInside(e.label, e.reverse_label)) {
      if (!parent.has(a.id)) parent.set(a.id, b.id);
    } else if (b.kind === "place" && a.kind !== "place") {
      addPerson(tree.get(b.id)!, e.reverse_label ?? e.label, a);
    } else if (a.kind === "place" && b.kind !== "place") {
      addPerson(tree.get(a.id)!, e.label, b);
    }
  }
  if (chapterAt) {
    for (const p of data.presence) {
      const who = node.get(p.entity_id);
      if (p.chapter_id === chapterAt && who && tree.has(p.place_id)) tree.get(p.place_id)!.here.push(who);
    }
  }
  // no cycles: a place whose chain of parents comes back to itself stays at the top
  const roots: PlaceNode[] = [];
  for (const p of places) {
    let up = parent.get(p.id);
    const seen = new Set([p.id]);
    while (up && !seen.has(up)) (seen.add(up), (up = parent.get(up)));
    const direct = parent.get(p.id);
    if (direct && !up) tree.get(direct)!.children.push(tree.get(p.id)!);
    else roots.push(tree.get(p.id)!);
  }
  const sort = (xs: PlaceNode[]) => {
    xs.sort((x, y) => x.name.localeCompare(y.name));
    for (const x of xs) sort(x.children);
  };
  sort(roots);
  return roots;
}

function addPerson(place: PlaceNode, label: string, who: { id: string; name: string; kind: string }) {
  const g = place.people.find((x) => x.label === label);
  if (g) g.who.push(who);
  else place.people.push({ label, who: [who] });
}
