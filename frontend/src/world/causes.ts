// Cause arrows on the Timeline (docs/SPEC.md §14.7): event–event relationships read as causes by their label, as the
// family tree reads parent types. "A caused B" and "B followed from A" both draw A → B, whatever the capitals; a
// renamed type still counts if it reads that way. Worked out when drawn, never stored.

import type { GraphData } from "./graph";

export interface CauseLink {
  /** the relationship's id */
  id: string;
  cause: string;
  effect: string;
  standing: string;
  /** how it reads from the cause: "caused", "led to" */
  reads: string;
}

const CAUSES = new Set(["caused", "led to"]);
const CAUSED_BY = new Set(["caused by", "followed from"]);
const norm = (s: string | null | undefined) => (s ?? "").split(/\s+/).filter(Boolean).join(" ").toLowerCase();

/** 1 when a type reads "A caused B" (A the cause), -1 when "B caused A", 0 when it isn't a cause (as on the server). */
export function causeDirection(label: string, reverse: string | null): number {
  const l = norm(label);
  const r = norm(reverse);
  if (CAUSES.has(l) || CAUSED_BY.has(r)) return 1;
  if (CAUSED_BY.has(l) || CAUSES.has(r)) return -1;
  return 0;
}

/** Every cause link between two events in the graph. */
export function causeLinks(graph: Pick<GraphData, "edges" | "nodes">): CauseLink[] {
  const isEvent = new Map(graph.nodes.map((n) => [n.id, n.kind === "event" || !!n.also_kinds?.includes("event")]));
  const out: CauseLink[] = [];
  for (const e of graph.edges) {
    const way = causeDirection(e.label, e.reverse_label);
    if (!way || !isEvent.get(e.a) || !isEvent.get(e.b)) continue;
    const [cause, effect] = way > 0 ? [e.a, e.b] : [e.b, e.a];
    const reads = way > 0 ? e.label : (e.reverse_label ?? e.label);
    out.push({ id: e.id, cause, effect, standing: e.standing, reads: norm(reads) || "caused" });
  }
  return out;
}

/** The links to draw for an event: its direct causes and effects, or with `whole` the whole chain, causes followed
 * back and effects forward, each event once (a loop stops where it closes), each step further a little fainter. */
export function linksOf(links: CauseLink[], id: string, whole: boolean): { link: CauseLink; depth: number }[] {
  if (!whole) return links.filter((l) => l.cause === id || l.effect === id).map((link) => ({ link, depth: 1 }));
  const out: { link: CauseLink; depth: number }[] = [];
  const taken = new Set<string>();
  for (const back of [true, false]) {
    const seen = new Set([id]);
    let frontier = [id];
    for (let depth = 1; frontier.length; depth++) {
      const next: string[] = [];
      for (const at of frontier) {
        for (const l of links) {
          if ((back ? l.effect : l.cause) !== at || taken.has(l.id)) continue;
          taken.add(l.id);
          out.push({ link: l, depth });
          const other = back ? l.cause : l.effect;
          if (!seen.has(other)) {
            seen.add(other);
            next.push(other);
          }
        }
      }
      frontier = next;
    }
  }
  return out;
}

/** An arrow's curve, from cause to effect, above the lane: a quadratic curve rising with the distance. */
export function arrowPath(x1: number, y1: number, x2: number, y2: number): string {
  const lift = Math.min(70, 18 + Math.abs(x2 - x1) / 6);
  const mx = (x1 + x2) / 2;
  const my = Math.min(y1, y2) - lift;
  return `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`;
}
