// The Timeline (docs/SPEC.md §13.2.2, §13.2.6), worked out in the browser from the cards, the timeline (chapters on
// the clock), the graph's relationships and the chronology ("is at", tellings). Pure functions: the model (marks on
// one axis, the book's band, eras, what is outside time and what isn't placed yet), lanes, an axis that is to scale
// except that long empty stretches fold to a fixed width, clusters (marks that would overlap, merged per lane), and
// ticks. TimelineView draws them; everything here is worked out once per change of data (the model) or once per zoom
// step (the clusters), so panning and zooming only move things.

import type { Chronology } from "../history";
import type { StoryChapter } from "../types";
import type { Card } from "./cards";
import { ageText, birthOf, deathOf, eventTime, type Era } from "./eras";
import type { GraphData } from "./graph";

export type MarkKind = "event" | "chapter" | "birth" | "death" | "move";

export interface Mark {
  id: string;
  kind: MarkKind;
  t: number;
  /** the end of a span (an event with an end) */
  t2: number | null;
  approx: boolean;
  label: string;
  /** what it opens: an entry's page, or a chapter in the editor */
  entity?: string;
  chapter?: string;
  /** the entries it is about, for filtering and lanes */
  about: string[];
  /** a chapter told as a tale or a flashback */
  told?: "tale" | "flashback";
  /** its place in book order (chapters), to order marks at the same time */
  book?: number;
}

export interface OutsideItem {
  id: string;
  label: string;
  entity?: string;
  chapter?: string;
  about: string[];
}

export interface TimelineModel {
  marks: Mark[];
  /** outside time: events and chapters, in book order (never on the axis, §13.1.8) */
  outside: OutsideItem[];
  /** events not placed yet, for the tray */
  unplaced: { id: string; name: string }[];
  eras: Era[];
  /** the book's band: its first to its last chapter by set time, tales and flashbacks aside */
  book: { start: number; end: number } | null;
  range: { min: number; max: number } | null;
  /** every time on the axis, sorted, for folding */
  times: number[];
}


export function buildModel(cards: Card[], timeline: StoryChapter[], eras: Era[], chron: Chronology | null): TimelineModel {
  const chapters = new Map(timeline.map((c) => [c.id, c]));
  const byId = new Map(cards.map((c) => [c.id, c]));
  const marks: Mark[] = [];
  const outside: OutsideItem[] = [];
  const unplaced: { id: string; name: string }[] = [];
  const eraIds = new Set(eras.map((e) => e.id));
  for (const c of cards) {
    if (c.kind === "event") {
      if (eraIds.has(c.id)) continue;
      const about = [c.id, ...c.relations.map((r) => r.other.id)];
      if (c.when?.outside) {
        outside.push({ id: `ev:${c.id}`, label: c.name, entity: c.id, about });
        continue;
      }
      const t = eventTime(c, chapters);
      if (!t) {
        // in a chapter with no set time is still placed (in the book), just not on the axis
        if (!c.when?.chapter) unplaced.push({ id: c.id, name: c.name });
        continue;
      }
      marks.push({ id: `ev:${c.id}`, kind: "event", t: t.t, t2: t.end, approx: t.approx, label: c.name, entity: c.id, about });
    } else if (c.kind === "character") {
      const birth = birthOf(c, byId, chapters);
      const death = deathOf(c, byId, chapters);
      if (birth) marks.push({ id: `born:${c.id}`, kind: "birth", t: birth.t, t2: null, approx: birth.approx, label: `${c.name} born`, entity: c.id, about: [c.id] });
      if (death) {
        const at = birth ? ageText(birth, null, death, { word: false }) : "";
        marks.push({ id: `died:${c.id}`, kind: "death", t: death.t, t2: null, approx: death.approx, label: `${c.name} dies${at ? ` at ${at}` : ""}`, entity: c.id, about: [c.id] });
      }
    }
  }
  const timed: Mark[] = [];
  for (const ch of timeline) {
    if (ch.outside_time) {
      outside.push({ id: `ch:${ch.id}`, label: `${ch.index + 1} · ${ch.title}`, chapter: ch.id, about: [] });
      continue;
    }
    if (ch.early || ch.clock === null || ch.set_time == null) continue;
    const m: Mark = { id: `ch:${ch.id}`, kind: "chapter", t: ch.set_time, t2: null, approx: !!ch.set_approx, label: `${ch.index + 1} · ${ch.title}${ch.told_as ? ` — ${ch.told_as}` : ""}`, chapter: ch.id, about: [], told: ch.told_as ?? undefined, book: ch.index };
    marks.push(m);
    if (!ch.told_as) timed.push(m);
  }
  for (const p of chron?.presence ?? []) {
    const ch = chapters.get(p.chapter_id);
    const who = byId.get(p.entity_id);
    const place = byId.get(p.place_id);
    if (!ch || !who || !place || ch.early || ch.clock === null || ch.set_time == null) continue;
    marks.push({ id: `mv:${p.entity_id}:${p.chapter_id}`, kind: "move", t: ch.set_time, t2: null, approx: !!ch.set_approx, label: `${who.name} at ${place.name}`, entity: who.id, chapter: ch.id, about: [who.id, place.id], book: ch.index });
  }
  const book = timed.length ? { start: Math.min(...timed.map((m) => m.t)), end: Math.max(...timed.map((m) => m.t)) } : null;
  const ts = new Set<number>();
  for (const m of marks) {
    ts.add(m.t);
    if (m.t2 != null) ts.add(m.t2);
  }
  for (const e of eras) {
    ts.add(e.start);
    if (e.end !== null) ts.add(e.end);
  }
  const times = [...ts].sort((a, b) => a - b);
  const range = times.length ? { min: times[0]!, max: times[times.length - 1]! } : null;
  marks.sort((a, b) => a.t - b.t || (a.book ?? 0) - (b.book ?? 0));
  return { marks, outside, unplaced: unplaced.sort((a, b) => a.name.localeCompare(b.name)), eras, book, range, times };
}

// ---- lanes ----------------------------------------------------------------------------------------------------

export interface Segment {
  t: number;
  t2: number;
  label: string;
  tone: "life" | "place" | "lives" | "role" | "era";
  /** fades out where the start or the end isn't known */
  fade?: "start" | "end" | "both";
  colour?: string;
}

export interface Lane {
  key: string;
  kind: "events" | "book" | "character" | "faction" | "era" | "entry";
  title: string;
  entity?: string;
  marks: Mark[];
  segments: Segment[];
  outside: OutsideItem[];
  /** "Seyla · 12 events · 4 places", for a lane folded to a line */
  counts: string;
}

export interface Filters {
  kinds: Set<MarkKind>;
  /** only marks about these entries (empty: all) */
  entries: Set<string>;
  /** relationships shown by standing (planned and rumoured as on the Graph) */
  standings: Set<string>;
}

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

/** The main lane, the book's lane, and a lane for each chosen entry (a character, a faction, an era, or another). */
export function buildLanes(model: TimelineModel, keys: string[], filters: Filters, cards: Map<string, Card>, timeline: StoryChapter[], graph: GraphData | null, chron: Chronology | null): Lane[] {
  const chapters = new Map(timeline.map((c) => [c.id, c]));
  const show = (m: Mark) => filters.kinds.has(m.kind) && (!filters.entries.size || m.about.some((a) => filters.entries.has(a)));
  // births, deaths and moves show in the main lane only when it is filtered to entries
  const main = model.marks.filter((m) => (m.kind === "event" || (filters.entries.size && m.kind !== "chapter")) && show(m));
  const lanes: Lane[] = [
    { key: "events", kind: "events", title: "Events", marks: main, segments: [], outside: model.outside.filter((o) => o.entity && (!filters.entries.size || o.about.some((a) => filters.entries.has(a)))), counts: plural(main.length, "event") },
    {
      key: "book", kind: "book", title: "The book", marks: filters.kinds.has("chapter") ? model.marks.filter((m) => m.kind === "chapter") : [],
      segments: model.book ? [{ t: model.book.start, t2: model.book.end, label: "the book", tone: "life" }] : [], outside: model.outside.filter((o) => o.chapter), counts: plural(model.marks.filter((m) => m.kind === "chapter").length, "chapter"),
    },
  ];
  const timeOfChapter = (id: string | null) => {
    const ch = id ? chapters.get(id) : undefined;
    return ch && !ch.early && ch.clock !== null && ch.set_time != null ? ch.set_time : null;
  };
  const spanOf = (e: { from_chapter_id: string | null; until_chapter_id: string | null; from_time?: number | null; until_time?: number | null }) => ({
    t: e.from_time ?? timeOfChapter(e.from_chapter_id),
    t2: e.until_time ?? timeOfChapter(e.until_chapter_id),
  });
  const lo = model.range?.min ?? 0;
  const hi = model.range?.max ?? 0;
  for (const key of keys) {
    const c = cards.get(key);
    if (c) lanes.push(entryLane(c));
    else if (model.eras.some((e) => e.id === key)) lanes.push(eraLane(key));
  }
  return lanes;

  function entryLane(c: Card): Lane {
    const era = model.eras.find((e) => e.id === c.id);
    if (era) return eraLane(era.id);
    const mine = model.marks.filter((m) => m.about.includes(c.id) && m.kind !== "chapter" && show(m));
    const segments: Segment[] = [];
    const outside = model.outside.filter((o) => o.about.includes(c.id));
    if (c.kind === "character") {
      const born = model.marks.find((m) => m.id === `born:${c.id}`);
      const died = model.marks.find((m) => m.id === `died:${c.id}`);
      if (born || died) segments.push({ t: born?.t ?? lo, t2: died?.t ?? hi, label: c.name, tone: "life", fade: born && died ? undefined : born ? "end" : "start" });
      // places over time: each run of chapters (in happened order) with the same "is at", one segment
      const here = (chron?.presence ?? []).filter((p) => p.entity_id === c.id && chapters.get(p.chapter_id)?.clock != null).sort((a, b) => chapters.get(a.chapter_id)!.clock! - chapters.get(b.chapter_id)!.clock!);
      let run: { place: string; t: number; t2: number } | null = null;
      for (const p of here) {
        const t = timeOfChapter(p.chapter_id);
        if (t === null) continue;
        if (run && run.place === p.place_id) run.t2 = t;
        else {
          if (run) segments.push({ t: run.t, t2: run.t2, label: cards.get(run.place)?.name ?? "?", tone: "place" });
          run = { place: p.place_id, t, t2: t };
        }
      }
      if (run) segments.push({ t: run.t, t2: run.t2, label: cards.get(run.place)?.name ?? "?", tone: "place" });
      // "lives in" spans, fainter
      for (const e of graph?.edges ?? []) {
        if (!filters.standings.has(e.standing)) continue;
        const reads = e.a === c.id ? e.label : e.b === c.id ? (e.reverse_label ?? e.label) : "";
        if (!/^lives in$/i.test(reads.trim())) continue;
        const s = spanOf(e);
        const other = cards.get(e.a === c.id ? e.b : e.a);
        segments.push({ t: s.t ?? lo, t2: s.t2 ?? hi, label: `lives in ${other?.name ?? "?"}`, tone: "lives", fade: s.t === null && s.t2 === null ? "both" : s.t === null ? "start" : s.t2 === null ? "end" : undefined });
      }
      const birth = birthOf(c, cards, chapters);
      const death = deathOf(c, cards, chapters);
      const marks = mine.map((m) => (m.kind === "event" && birth ? { ...m, label: `${m.label}${ageLabel(ageText(birth, death, { t: m.t, approx: m.approx }))}` } : m));
      const places = new Set(segments.filter((s) => s.tone === "place").map((s) => s.label)).size;
      return { key: c.id, kind: "character", title: c.name, entity: c.id, marks, segments, outside, counts: `${c.name} · ${plural(mine.filter((m) => m.kind === "event").length, "event")} · ${plural(places, "place")}` };
    }
    if (c.kind === "faction") {
      // members joining and leaving, and who held each role when
      const extra: Mark[] = [];
      for (const e of graph?.edges ?? []) {
        if (!filters.standings.has(e.standing) || (e.a !== c.id && e.b !== c.id)) continue;
        const who = cards.get(e.a === c.id ? e.b : e.a);
        if (!who || who.kind !== "character") continue;
        const s = spanOf(e);
        const role = e.role ?? relRole(c, who.id);
        if (role) segments.push({ t: s.t ?? lo, t2: s.t2 ?? hi, label: `${role}: ${who.name}`, tone: "role", fade: s.t === null ? "start" : s.t2 === null ? "end" : undefined });
        if (s.t !== null && filters.kinds.has("move")) extra.push({ id: `join:${e.id}`, kind: "move", t: s.t, t2: null, approx: false, label: `${who.name} joins${role ? ` · ${role}` : ""}`, entity: who.id, about: [who.id, c.id] });
        if (s.t2 !== null && filters.kinds.has("move")) extra.push({ id: `leave:${e.id}`, kind: "move", t: s.t2, t2: null, approx: false, label: `${who.name} leaves${role ? ` · ${role}` : ""}`, entity: who.id, about: [who.id, c.id] });
      }
      const marks = [...mine, ...extra].sort((a, b) => a.t - b.t);
      return { key: c.id, kind: "faction", title: c.name, entity: c.id, marks, segments, outside, counts: `${c.name} · ${plural(mine.filter((m) => m.kind === "event").length, "event")} · ${plural(extra.length, "change")}` };
    }
    return { key: c.id, kind: "entry", title: c.name, entity: c.id, marks: mine, segments, outside, counts: `${c.name} · ${plural(mine.length, "mark")}` };
  }

  function relRole(faction: Card, who: string): string | undefined {
    return faction.relations.find((r) => r.other.id === who && r.role)?.role;
  }

  function eraLane(id: string): Lane {
    const era = model.eras.find((e) => e.id === id)!;
    const end = era.end ?? Infinity;
    const marks = model.marks.filter((m) => m.kind === "event" && m.t >= era.start && m.t <= end && show(m));
    const nested = model.eras.filter((e) => e.id !== id && e.start >= era.start && (e.end ?? Infinity) <= end);
    return {
      key: id, kind: "era", title: era.name, entity: id, marks,
      segments: [{ t: era.start, t2: era.end ?? hi, label: era.name, tone: "era", colour: era.colour, fade: era.end === null ? "end" : undefined }, ...nested.map((e) => ({ t: e.start, t2: e.end ?? hi, label: e.name, tone: "era" as const, colour: e.colour }))],
      outside: [], counts: `${era.name} · ${plural(marks.length, "event")}${nested.length ? ` · ${plural(nested.length, "era")}` : ""}`,
    };
  }
}

const ageLabel = (a: string) => (a && a !== "not born yet" && !a.startsWith("died") ? ` (${a.replace(/^age /, "")})` : "");

// ---- the axis ---------------------------------------------------------------------------------------------------

/** A stretch with nothing in it wider than this many pixels folds to FOLD_W, labelled with its length (the page
 * passes a threshold from its width: a quarter of it, within 160–360). */
export const FOLD_AT = 220;
export const FOLD_W = 96;
export const foldAtFor = (width: number) => Math.min(360, Math.max(160, width / 4));

export interface Fold {
  t1: number;
  t2: number;
  x: number;
  w: number;
  length: number;
}

export interface Axis {
  /** pixels per unit of time, where the axis is to scale */
  k: number;
  x: (t: number) => number;
  t: (x: number) => number;
  folds: Fold[];
  width: number;
}

/** An axis at scale `k` over these (sorted) times: to scale, except that empty stretches wider than `foldAt` fold. */
export function makeAxis(times: number[], k: number, pad = 0, foldAt = FOLD_AT): Axis {
  const ts = times.length ? times : [0];
  const xs: number[] = new Array(ts.length);
  const folds: Fold[] = [];
  let x = pad;
  xs[0] = x;
  for (let i = 1; i < ts.length; i++) {
    const gap = (ts[i]! - ts[i - 1]!) * k;
    if (gap > foldAt) {
      folds.push({ t1: ts[i - 1]!, t2: ts[i]!, x, w: FOLD_W, length: ts[i]! - ts[i - 1]! });
      x += FOLD_W;
    } else x += gap;
    xs[i] = x;
  }
  const first = ts[0]!;
  const last = ts[ts.length - 1]!;
  const width = x + pad;
  const find = (t: number) => {
    let lo = 0;
    let hi = ts.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (ts[mid]! <= t) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  };
  const toX = (t: number) => {
    if (t <= first) return xs[0]! - (first - t) * k;
    if (t >= last) return xs[ts.length - 1]! + (t - last) * k;
    const i = find(t);
    const a = ts[i]!;
    const b = ts[i + 1]!;
    return xs[i]! + ((t - a) / (b - a)) * (xs[i + 1]! - xs[i]!);
  };
  const toT = (px: number) => {
    if (px <= xs[0]!) return first - (xs[0]! - px) / k;
    if (px >= xs[ts.length - 1]!) return last + (px - xs[ts.length - 1]!) / k;
    let lo = 0;
    let hi = ts.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (xs[mid]! <= px) lo = mid;
      else hi = mid - 1;
    }
    const a = xs[lo]!;
    const b = xs[lo + 1]!;
    return b === a ? ts[lo]! : ts[lo]! + ((px - a) / (b - a)) * (ts[lo + 1]! - ts[lo]!);
  };
  return { k, x: toX, t: toT, folds, width };
}

/** The scale at which everything fits in `width` pixels and fills as much of it as it can. Folds make the width
 * jump as the scale grows (a stretch folds, and the axis gets narrower), so the scales are swept rather than halved:
 * from the one where nothing folds to a hundred thousand times that, the fullest that fits; the first of equals. */
export function fitScale(times: number[], width: number, pad = 40, foldAt = FOLD_AT): number {
  if (times.length < 2) return 1;
  const span = times[times.length - 1]! - times[0]!;
  const k0 = Math.max(1e-9, (width - 2 * pad) / Math.max(span, 1e-9));
  let best = k0;
  let bestW = -1;
  for (let i = 0; i <= 300; i++) {
    const k = k0 * Math.pow(1e5, i / 300);
    const w = makeAxis(times, k, pad, foldAt).width;
    if (w <= width && w > bestW + 0.5) {
      best = k;
      bestW = w;
    }
  }
  return best;
}

/** Zoom steps: clusters are worked out again only when the scale crosses one (a step is a factor of √2). */
export const stepOf = (k: number) => Math.round(Math.log2(k) * 2);
export const scaleOfStep = (s: number) => Math.pow(2, s / 2);

// ---- clusters ---------------------------------------------------------------------------------------------------

export interface Cluster {
  id: string;
  t: number;
  marks: Mark[];
  /** "14 events · 3 births · 2 moves" */
  breakdown: string;
}

export type Item = { mark: Mark; cluster?: undefined } | { cluster: Cluster; mark?: undefined };

const KIND_WORDS: Record<MarkKind, string> = { event: "event", chapter: "chapter", birth: "birth", death: "death", move: "move" };

export function breakdown(marks: Mark[]): string {
  const n = new Map<MarkKind, number>();
  for (const m of marks) n.set(m.kind, (n.get(m.kind) ?? 0) + 1);
  return (["event", "chapter", "birth", "death", "move"] as MarkKind[]).filter((k) => n.get(k)).map((k) => plural(n.get(k)!, KIND_WORDS[k])).join(" · ");
}

/** Marks that would overlap at this axis, merged into clusters with a count and a breakdown. A cluster is never
 * wider than `minGap` (measured from its first mark), so a dense stretch is several clusters, not one. */
export function cluster(marks: Mark[], axis: Axis, minGap = 14): Item[] {
  const out: Item[] = [];
  let group: Mark[] = [];
  let firstX = -Infinity;
  const flush = () => {
    if (!group.length) return;
    if (group.length === 1) out.push({ mark: group[0]! });
    else {
      // drawn in the middle of its window, so two clusters are never closer than the gap
      const t = Math.min(group[group.length - 1]!.t, Math.max(group[0]!.t, axis.t(firstX + minGap / 2)));
      out.push({ cluster: { id: `cl:${group[0]!.id}:${group.length}`, t, marks: group, breakdown: breakdown(group) } });
    }
    group = [];
  };
  for (const m of marks) {
    const x = axis.x(m.t);
    if (x - firstX >= minGap) {
      flush();
      firstX = x;
    }
    group.push(m);
  }
  flush();
  return out;
}

// ---- ticks ------------------------------------------------------------------------------------------------------

/** Round times to label along the visible part of the axis, at least `minPx` apart, never inside a fold. */
export function ticks(axis: Axis, x0: number, x1: number, minPx = 90): number[] {
  const step = (() => {
    const raw = minPx / Math.max(axis.k, 1e-12);
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const m of [1, 2, 5, 10]) if (m * p >= raw) return m * p;
    return 10 * p;
  })();
  const t0 = axis.t(x0);
  const t1 = axis.t(x1);
  const out: number[] = [];
  for (let t = Math.ceil(t0 / step) * step; t <= t1 && out.length < 200; t += step) {
    if (axis.folds.some((f) => t > f.t1 && t < f.t2)) continue;
    out.push(Number(t.toFixed(6)));
  }
  return out;
}

/** What a brushed span holds, per kind (In this span). */
export function inSpan(marks: Mark[], from: number, to: number): Mark[] {
  return marks.filter((m) => m.t <= to && (m.t2 ?? m.t) >= from);
}
