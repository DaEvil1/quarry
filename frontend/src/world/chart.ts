// The chart (docs/SPEC.md §13.7): a schematic map of the world's places, worked out in the browser from the graph's
// relationships, the cards (a place's type) and the pins. Pure functions: the state as of a point (what is inside
// what, borders, routes, directions, who controls and who is there), shapes from types, a layout from the inside
// out (each container's contents packed with d3-force, seeded, run to rest, pinned places fixed; a container as large
// as what it holds), absolute positions, and what changed across a span. ChartView draws the result.

import { forceCollide, forceLink, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";

import type { Card } from "./cards";
import type { GraphData } from "./graph";
import { holds, norm, type At, type IndexOf } from "./time";

export type Shape = "world" | "hexagon" | "circle" | "rounded" | "square" | "water" | "ribbon" | "island" | "triangle" | "scalloped" | "dotted" | "plane" | "none";
export const SHAPES: Shape[] = ["world", "hexagon", "circle", "rounded", "square", "water", "ribbon", "island", "triangle", "scalloped", "dotted", "plane"];
export const SHAPE_WORDS: Record<Shape, string> = {
  world: "the world", hexagon: "hexagon (a land)", circle: "circle (a settlement)", rounded: "rounded square (a district)", square: "square (a building)",
  water: "water", ribbon: "ribbon (a river)", island: "island", triangle: "triangle (a mountain)", scalloped: "scalloped (a forest)", dotted: "dotted (a reef)",
  plane: "a plane apart", none: "no type",
};

/** The list in the code (§13.7.2), with its synonyms. A world adds its own in the chart's settings. */
const TYPES: Record<string, Shape> = {
  world: "world",
  land: "hexagon", region: "hexagon", realm: "hexagon", kingdom: "hexagon", country: "hexagon", province: "hexagon",
  city: "circle", town: "circle", village: "circle", port: "circle", fort: "circle", hamlet: "circle",
  district: "rounded",
  building: "square", room: "square",
  sea: "water", lake: "water", ocean: "water", bay: "water",
  river: "ribbon",
  island: "island",
  mountain: "triangle",
  forest: "scalloped",
  reef: "dotted",
  plane: "plane",
};

/** How deep a type sits, for "down to": lands 1, settlements 2, buildings 3, rooms 4. */
const LEVEL: Record<string, number> = { district: 3, building: 3, room: 4 };
export const DEPTHS = [
  { value: 1, label: "lands" },
  { value: 2, label: "settlements" },
  { value: 3, label: "buildings" },
  { value: 4, label: "rooms" },
];

export interface Pin {
  place_id: string;
  container_id: string | null;
  x: number;
  y: number;
}

export const pinKey = (place: string, container: string | null) => `${place}|${container ?? ""}`;

// ---- the state as of a point ------------------------------------------------------------------------------------

type Edge = GraphData["edges"][number];
const isInside = (label: string, reverse: string | null) => /^(inside|in|part of|within)$/i.test(label) || /^contains$/i.test(reverse ?? "");
const reads = (e: Edge, re: RegExp) => re.test(e.label.trim()) || re.test((e.reverse_label ?? "").trim());

export interface ChartPlace {
  id: string;
  name: string;
  /** its type value as written, and the shape it maps to */
  type: string | null;
  shape: Shape;
  level: number;
  parent: string | null;
  /** other containers it is also recorded inside (drawn in the first) */
  alsoIn: string[];
  children: string[];
  /** mentions, in the three steps of the mentions strip (0 when never named) */
  step: number;
}

export interface Route {
  a: string;
  b: string;
  kind: "road" | "sea";
  standing: string;
}

export interface ChartState {
  places: Map<string, ChartPlace>;
  roots: string[];
  borders: { a: string; b: string; standing: string }[];
  routes: Route[];
  /** a north of b; a west of b */
  north: [string, string][];
  west: [string, string][];
  /** each place's controlling factions, and the factions in order of how much they control */
  control: Map<string, string[]>;
  factions: string[];
  /** who is there: "is at" in the chosen chapter, else "lives in" */
  here: Map<string, string[]>;
}

export interface StateInput {
  data: GraphData;
  cards: Map<string, Card>;
  /** the cards' facts as of the point (the type that holds then) */
  typeOf: (id: string) => string[];
  shapes: Record<string, string>;
  mentions: Map<string, number>;
  asOf: At | null;
  indexOf: IndexOf;
  /** the chapter chosen, for "is at" */
  chapter: string | null;
  standings: Set<string>;
}

export function shapeOf(types: string[], own: Record<string, string>): { type: string | null; shape: Shape } {
  for (const t of types) {
    const k = norm(t);
    const s = (own[k] as Shape | undefined) ?? TYPES[k];
    if (s) return { type: t, shape: s };
  }
  return { type: types[0] ?? null, shape: "none" };
}

export function chartState(inp: StateInput): ChartState {
  const { data, asOf, indexOf } = inp;
  const node = new Map(data.nodes.map((n) => [n.id, n]));
  const placeIds = data.nodes.filter((n) => n.kind === "place").map((n) => n.id);
  const busiest = Math.max(0, ...placeIds.map((id) => inp.mentions.get(id) ?? 0));
  const step = (n: number) => (n <= 0 || busiest <= 0 ? 0 : Math.min(3, Math.max(1, Math.ceil((3 * n) / busiest))));
  const places = new Map<string, ChartPlace>();
  for (const id of placeIds) {
    const { type, shape } = shapeOf(inp.typeOf(id), inp.shapes);
    places.set(id, { id, name: node.get(id)!.name, type, shape, level: type ? (LEVEL[norm(type)] ?? (shape === "circle" ? 2 : shape === "square" ? 3 : 1)) : 0, parent: null, alsoIn: [], children: [], step: step(inp.mentions.get(id) ?? 0) });
  }
  const now = (e: Edge) => inp.standings.has(e.standing) && (asOf === null || holds(e, asOf, indexOf));
  const state: ChartState = { places, roots: [], borders: [], routes: [], north: [], west: [], control: new Map(), factions: [], here: new Map() };
  const parents = new Map<string, string[]>();
  const counts = new Map<string, number>();
  for (const e of data.edges) {
    if (!now(e)) continue;
    const a = node.get(e.a);
    const b = node.get(e.b);
    if (!a || !b) continue;
    if (a.kind === "place" && b.kind === "place") {
      if (isInside(e.label, e.reverse_label)) parents.set(a.id, [...(parents.get(a.id) ?? []), b.id]);
      else if (/^borders$/i.test(e.label.trim())) state.borders.push({ a: a.id, b: b.id, standing: e.standing });
      else if (reads(e, /^road to$/i)) state.routes.push({ a: a.id, b: b.id, kind: "road", standing: e.standing });
      else if (reads(e, /^sea route to$/i)) state.routes.push({ a: a.id, b: b.id, kind: "sea", standing: e.standing });
      else if (/^north of$/i.test(e.label.trim())) state.north.push([a.id, b.id]);
      else if (/^south of$/i.test(e.label.trim())) state.north.push([b.id, a.id]);
      else if (/^west of$/i.test(e.label.trim())) state.west.push([a.id, b.id]);
      else if (/^east of$/i.test(e.label.trim())) state.west.push([b.id, a.id]);
    } else if (a.kind === "faction" && b.kind === "place" && /^controls$/i.test(e.label.trim())) {
      state.control.set(b.id, [...(state.control.get(b.id) ?? []), a.id]);
      counts.set(a.id, (counts.get(a.id) ?? 0) + 1);
    } else if (b.kind === "place" && a.kind === "character" && /^lives in$/i.test(e.label.trim()) && !inp.chapter) {
      state.here.set(b.id, [...(state.here.get(b.id) ?? []), a.id]);
    }
  }
  if (inp.chapter) {
    for (const p of data.presence) if (p.chapter_id === inp.chapter && places.has(p.place_id)) state.here.set(p.place_id, [...(state.here.get(p.place_id) ?? []), p.entity_id]);
  }
  state.factions = [...counts.entries()].sort((x, y) => y[1] - x[1] || (node.get(x[0])?.name ?? "").localeCompare(node.get(y[0])?.name ?? "")).map(([id]) => id);
  // drawn in the first container recorded, as the place tree does; no cycles; planes stand apart
  for (const [id, ps] of parents) {
    const first = ps.find((p) => places.has(p));
    if (!first) continue;
    let up: string | undefined = first;
    const seen = new Set([id]);
    while (up && !seen.has(up)) (seen.add(up), (up = parents.get(up)?.[0]));
    if (up) continue;
    places.get(id)!.parent = first;
    places.get(id)!.alsoIn = ps.filter((p) => p !== first && places.has(p));
  }
  for (const p of places.values()) {
    if (p.parent) places.get(p.parent)!.children.push(p.id);
    else state.roots.push(p.id);
  }
  // untyped places take their depth from their container
  const depthOf = (p: ChartPlace): number => (p.level ? p.level : p.parent ? Math.min(4, depthOf(places.get(p.parent)!) + 1) : 1);
  for (const p of places.values()) if (!p.level) p.level = depthOf(p);
  const byName = (x: string, y: string) => places.get(x)!.name.localeCompare(places.get(y)!.name);
  state.roots.sort(byName);
  for (const p of places.values()) p.children.sort(byName);
  return state;
}

// ---- layout -------------------------------------------------------------------------------------------------------

export interface Laid {
  id: string;
  /** relative to its container's centre */
  x: number;
  y: number;
  r: number;
  /** absolute */
  ax: number;
  ay: number;
  pinned: boolean;
}

export interface Layout {
  laid: Map<string, Laid>;
  /** directions it couldn't honour */
  unplaced: string[];
  bounds: { x: number; y: number; w: number; h: number };
}

const LEAF = [16, 18, 21, 25];
const PAD = 14;

interface N extends SimulationNodeDatum {
  id: string;
  r: number;
}

/** Lay the chart out from the inside out. `visible` decides which places are drawn (filters); hidden ones are left out
 * of the layout too. */
export function layoutChart(state: ChartState, pins: Map<string, Pin>, visible: (id: string) => boolean = () => true): Layout {
  const laid = new Map<string, Laid>();
  const { places } = state;
  const unplaced: string[] = [];
  // a link between two places, lifted to the pair of their ancestors that share a container
  const chain = (id: string) => {
    const out = [id];
    let p = places.get(id)?.parent ?? null;
    while (p) (out.push(p), (p = places.get(p)?.parent ?? null));
    return out;
  };
  const lift = (a: string, b: string): [string, string] | null => {
    const ca = chain(a);
    const cb = chain(b);
    for (let i = 0; i < ca.length; i++) {
      const j = cb.findIndex((x) => (places.get(x)?.parent ?? null) === (places.get(ca[i]!)?.parent ?? null));
      if (j >= 0 && ca[i] !== cb[j]) return [ca[i]!, cb[j]!];
    }
    return null;
  };
  const borders = state.borders.map((b) => lift(b.a, b.b)).filter((x): x is [string, string] => !!x);
  const roads = state.routes.map((r) => lift(r.a, r.b)).filter((x): x is [string, string] => !!x);
  const north = state.north.map(([a, b]) => lift(a, b)).filter((x): x is [string, string] => !!x);
  const west = state.west.map(([a, b]) => lift(a, b)).filter((x): x is [string, string] => !!x);
  const contradictory = new Set<string>();
  for (const [a, b] of north) if (north.some(([c, d]) => c === b && d === a)) contradictory.add([a, b].sort().join("|"));
  for (const [a, b] of west) if (west.some(([c, d]) => c === b && d === a)) contradictory.add([a, b].sort().join("|"));

  /** lays out a container's contents (or the top level) and answers with the radius they need */
  function pack(container: string | null, ids: string[]): number {
    const kids = ids.filter(visible);
    for (const id of kids) {
      const p = places.get(id)!;
      const inner = p.children.filter(visible);
      laid.set(id, { id, x: 0, y: 0, r: inner.length ? pack(id, inner) : LEAF[p.step]! * (p.shape === "none" ? 0.8 : 1), ax: 0, ay: 0, pinned: false });
    }
    if (!kids.length) return 0;
    const set = new Set(kids);
    const nodes: N[] = kids.map((id, i) => {
      const l = laid.get(id)!;
      const pin = pins.get(pinKey(id, container));
      // start on a circle (seeded: the same data gives the same chart)
      const a = (i / kids.length) * Math.PI * 2;
      const n: N = { id, r: l.r, x: Math.cos(a) * l.r * 2, y: Math.sin(a) * l.r * 2 };
      if (pin) {
        n.fx = pin.x;
        n.fy = pin.y;
        l.pinned = true;
      }
      return n;
    });
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const links = [
      ...borders.filter(([a, b]) => set.has(a) && set.has(b)).map(([a, b]) => ({ source: a, target: b, d: 0, s: 0.9 })),
      ...roads.filter(([a, b]) => set.has(a) && set.has(b)).map(([a, b]) => ({ source: a, target: b, d: 0.6, s: 0.2 })),
    ];
    const dirs = [
      ...north.filter(([a, b]) => set.has(a) && set.has(b) && !contradictory.has([a, b].sort().join("|"))).map(([a, b]) => ({ a, b, axis: "y" as const })),
      ...west.filter(([a, b]) => set.has(a) && set.has(b) && !contradictory.has([a, b].sort().join("|"))).map(([a, b]) => ({ a, b, axis: "x" as const })),
    ];
    // keep directions: a north of b sits above it (a west of b to its left)
    const direction = (alpha: number) => {
      for (const d of dirs) {
        const a = byId.get(d.a)!;
        const b = byId.get(d.b)!;
        const gap = (a.r + b.r) * 0.9;
        const k = d.axis === "y" ? "y" : "x";
        const v = k === "y" ? "vy" : "vx";
        const diff = (b[k] ?? 0) - (a[k] ?? 0);
        if (diff < gap) {
          const push = (gap - diff) * 0.5 * alpha;
          a[v] = (a[v] ?? 0) - push;
          b[v] = (b[v] ?? 0) + push;
        }
      }
    };
    const sim = forceSimulation(nodes)
      .force("link", forceLink<N, { source: string; target: string; d: number; s: number }>(links).id((n) => n.id)
        .distance((l) => ((l.source as unknown as N).r + (l.target as unknown as N).r) * (1 + l.d))
        .strength((l) => l.s))
      .force("collide", forceCollide<N>((n) => n.r + 4).strength(1).iterations(3))
      .force("x", forceX(0).strength(0.06))
      .force("y", forceY(0).strength(0.06))
      .force("dir", direction)
      .stop();
    sim.tick(Math.min(400, 120 + nodes.length * 8));
    // directions it couldn't keep
    for (const d of dirs) {
      const a = byId.get(d.a)!;
      const b = byId.get(d.b)!;
      const ok = d.axis === "y" ? (a.y ?? 0) < (b.y ?? 0) : (a.x ?? 0) < (b.x ?? 0);
      if (!ok) unplaced.push(`${places.get(d.a)!.name} ${d.axis === "y" ? "north" : "west"} of ${places.get(d.b)!.name}`);
    }
    // centre what isn't pinned on the contents, then the container's radius from what it holds
    const free = nodes.filter((n) => n.fx == null);
    if (free.length === nodes.length) {
      const cx = nodes.reduce((s, n) => s + (n.x ?? 0), 0) / nodes.length;
      const cy = nodes.reduce((s, n) => s + (n.y ?? 0), 0) / nodes.length;
      for (const n of nodes) (n.x = (n.x ?? 0) - cx), (n.y = (n.y ?? 0) - cy);
    }
    let r = 0;
    for (const n of nodes) {
      const l = laid.get(n.id)!;
      l.x = n.fx ?? n.x ?? 0;
      l.y = n.fy ?? n.y ?? 0;
      r = Math.max(r, Math.hypot(l.x, l.y) + l.r);
    }
    return r + PAD + (container ? 12 : 0);
  }

  // the top level: everything not in a plane (framed by a "world" when there is one), then each plane off to the side
  const roots = state.roots.filter(visible);
  const planes = roots.filter((id) => places.get(id)!.shape === "plane");
  const main = roots.filter((id) => places.get(id)!.shape !== "plane");
  const mainR = pack(null, main);
  let px = mainR + 60;
  for (const id of planes) {
    const p = places.get(id)!;
    const r = p.children.filter(visible).length ? pack(id, p.children) : LEAF[p.step]!;
    const pin = pins.get(pinKey(id, null));
    laid.set(id, { id, x: pin?.x ?? px + r, y: pin?.y ?? 0, r, ax: 0, ay: 0, pinned: !!pin });
    px += 2 * r + 60;
  }
  // absolute positions
  const place = (id: string, ox: number, oy: number) => {
    const l = laid.get(id);
    if (!l) return;
    l.ax = ox + l.x;
    l.ay = oy + l.y;
    for (const c of places.get(id)!.children) place(c, l.ax, l.ay);
  };
  for (const id of roots) place(id, 0, 0);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const l of laid.values()) {
    x0 = Math.min(x0, l.ax - l.r);
    y0 = Math.min(y0, l.ay - l.r);
    x1 = Math.max(x1, l.ax + l.r);
    y1 = Math.max(y1, l.ay + l.r);
  }
  if (!laid.size) (x0 = -100), (y0 = -100), (x1 = 100), (y1 = 100);
  for (const k of contradictory) {
    const [a, b] = k.split("|");
    unplaced.push(`${places.get(a!)?.name} and ${places.get(b!)?.name} (each recorded on the other's side)`);
  }
  return { laid, unplaced: [...new Set(unplaced)], bounds: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } };
}

/** Every place inside this one, at any depth (for Reset inside…). */
export function inside(state: ChartState, id: string): string[] {
  const out: string[] = [];
  const walk = (x: string) => {
    for (const c of state.places.get(x)?.children ?? []) (out.push(c), walk(c));
  };
  walk(id);
  return out;
}

/** How many places a container holds, at any depth ("Old Harbour · 2 places"). */
export const holdsCount = (state: ChartState, id: string) => inside(state, id).length;

// ---- shapes -------------------------------------------------------------------------------------------------------

/** An SVG path for a shape of radius r centred on 0,0. */
export function shapePath(shape: Shape, r: number, container: boolean): string {
  const poly = (n: number, rot: number, rr = r) =>
    Array.from({ length: n }, (_, i) => {
      const a = rot + (i / n) * Math.PI * 2;
      return `${i ? "L" : "M"}${(Math.cos(a) * rr).toFixed(1)} ${(Math.sin(a) * rr).toFixed(1)}`;
    }).join(" ") + " Z";
  const roundRect = (w: number, h: number, c: number) =>
    `M${-w + c} ${-h} H${w - c} Q${w} ${-h} ${w} ${-h + c} V${h - c} Q${w} ${h} ${w - c} ${h} H${-w + c} Q${-w} ${h} ${-w} ${h - c} V${-h + c} Q${-w} ${-h} ${-w + c} ${-h} Z`;
  const blob = (rr: number, wob: number) =>
    Array.from({ length: 12 }, (_, i) => {
      const a = (i / 12) * Math.PI * 2;
      const k = rr * (1 + (i % 2 ? wob : -wob * 0.6));
      return [Math.cos(a) * k, Math.sin(a) * k];
    }).reduce((d, [x, y], i, ps) => {
      const [nx, ny] = ps[(i + 1) % ps.length]!;
      const mx = (x! + nx!) / 2;
      const my = (y! + ny!) / 2;
      return `${d}${i ? "" : `M${((x! + ps[ps.length - 1]![0]!) / 2).toFixed(1)} ${((y! + ps[ps.length - 1]![1]!) / 2).toFixed(1)} `}Q${x!.toFixed(1)} ${y!.toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)} `;
    }, "") + "Z";
  switch (shape) {
    case "world":
    case "hexagon":
      return poly(6, Math.PI / 6, r / Math.cos(Math.PI / 6));
    case "circle":
      return `M${-r} 0 A${r} ${r} 0 1 0 ${r} 0 A${r} ${r} 0 1 0 ${-r} 0 Z`;
    case "rounded":
      return roundRect(r * 0.9, r * 0.9, r * 0.3);
    case "square":
      return `M${-r * 0.88} ${-r * 0.88} H${r * 0.88} V${r * 0.88} H${-r * 0.88} Z`;
    case "water":
    case "island":
    case "dotted":
      return blob(r * 1.02, 0.06);
    case "ribbon":
      return roundRect(r * 1.25, r * 0.45, r * 0.45);
    case "triangle":
      return `M0 ${-r * 1.1} L${r * 1.05} ${r * 0.75} L${-r * 1.05} ${r * 0.75} Z`;
    case "scalloped":
      return Array.from({ length: 10 }, (_, i) => {
        const a1 = (i / 10) * Math.PI * 2;
        const a2 = ((i + 1) / 10) * Math.PI * 2;
        const x2 = Math.cos(a2) * r * 0.92;
        const y2 = Math.sin(a2) * r * 0.92;
        return `${i ? "" : `M${(Math.cos(a1) * r * 0.92).toFixed(1)} ${(Math.sin(a1) * r * 0.92).toFixed(1)} `}A${(r * 0.3).toFixed(1)} ${(r * 0.3).toFixed(1)} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)} `;
      }).join("") + "Z";
    case "plane":
      return blob(r, 0.04);
    case "none":
    default:
      return container ? roundRect(r * 0.95, r * 0.85, r * 0.25) : roundRect(r * 0.85, r * 0.85, r * 0.35);
  }
}

// ---- what changed across a span (§13.7.5) -------------------------------------------------------------------------

export interface Change {
  place: string;
  text: string;
  /** where on the clock it happened, for ordering and the scrubber */
  t: number;
  when: string;
}

/** Each place's controlling factions, container and borders, compared between two states. */
export function changesBetween(a: ChartState, b: ChartState, name: (id: string) => string): { place: string; parts: string[] }[] {
  const out: { place: string; parts: string[] }[] = [];
  const list = (xs: string[]) => (xs.length ? xs.map(name).join(" and ") : "no one");
  const bordersOf = (s: ChartState, id: string) => new Set(s.borders.filter((x) => x.a === id || x.b === id).map((x) => (x.a === id ? x.b : x.a)));
  for (const id of b.places.keys()) {
    const parts: string[] = [];
    const ca = [...(a.control.get(id) ?? [])].sort();
    const cb = [...(b.control.get(id) ?? [])].sort();
    if (ca.join() !== cb.join()) parts.push(`controlled by ${list(ca)} → ${list(cb)}`);
    const pa = a.places.get(id)?.parent ?? null;
    const pb = b.places.get(id)?.parent ?? null;
    if (pa !== pb) parts.push(pb ? `now inside ${name(pb)}${pa ? ` (was ${name(pa)})` : ""}` : `no longer inside ${name(pa!)}`);
    const ba = bordersOf(a, id);
    const bb = bordersOf(b, id);
    for (const x of ba) if (!bb.has(x) && name(id) > name(x)) parts.push(`no longer borders ${name(x)}`);
    for (const x of bb) if (!ba.has(x) && name(id) > name(x)) parts.push(`now borders ${name(x)}`);
    if (parts.length) out.push({ place: id, parts });
  }
  return out;
}
