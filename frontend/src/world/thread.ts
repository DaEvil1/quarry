// Reading one entry's thread (docs/SPEC.md §11.4): the paragraphs (or chapters) that name an entry, in story order,
// worked out in the browser from the chapters kept on the device and the same matcher that colours names, so it
// works on the phone without a network. With a second entry, only what names both.
//
// A paragraph is a line, as in the companion. A margin note (%% line) right before or after a shown paragraph comes
// with it, and a margin note that names the entry (both entries) is a hit of its own. A shared name is settled by the
// choice lines above it (docs/SPEC.md §14.10); where none does, the paragraph is left out and counted as unsettled.

import type { Hit, Matcher } from "./matcher";

export interface ThreadChapter {
  id: string;
  title: string;
  body: string;
  state: "current" | "experiment" | "retired";
  project: string;
  project_name: string;
}

export interface Para {
  kind: "para";
  /** where the line starts in the chapter, to open the editor there */
  from: number;
  text: string;
  hits: Hit[];
  margin: boolean;
  /** names the entry (or both): false for a margin note shown because it sits next to one */
  hit: boolean;
  /** shared names no choice line settles here (each with its claimants) */
  vague?: Hit[];
}

export interface Gap {
  kind: "gap";
  /** the paragraphs left out between two shown ones, to open in place */
  paras: Para[];
}

export interface ThreadPart {
  chapter: ThreadChapter;
  blocks: (Para | Gap)[];
  /** hit paragraphs in this chapter */
  count: number;
}

/** Paragraphs left out because a shared name in them isn't settled: how many, and the name ("Isolde"). */
export interface Unsettled {
  paragraphs: number;
  form: string;
}

const MARGIN = /^[ \t]*%%/;

/** Every paragraph of a chapter with the names in it (likely misspellings aside), shared names settled by the choice
 * lines; a choice line itself names nobody. */
export function paragraphs(body: string, matcher: Matcher): Para[] {
  const out: Para[] = [];
  const choices = matcher.choices(body);
  const isChoice = new Set(choices.map((c) => c.start));
  let from = 0;
  for (const line of body.split("\n")) {
    if (line.trim()) {
      const all = isChoice.has(from) ? [] : matcher.resolve(matcher.scanLine(line, from, false), choices);
      const hits = all.filter((h) => h.kind !== "near_miss" && h.kind !== "ambiguous");
      // a name settled for several entries counts for each
      for (const h of all) for (const id of h.chosen?.slice(1) ?? []) hits.push({ ...h, entityId: id });
      const vague = all.filter((h) => h.kind === "ambiguous");
      out.push({ kind: "para", from, text: line, hits, margin: MARGIN.test(line), hit: false, ...(vague.length ? { vague } : {}) });
    }
    from += line.length + 1;
  }
  return out;
}

const names = (p: Para, ids: string[]) => ids.every((id) => p.hits.some((h) => h.entityId === id));

/** Would this paragraph name them all, if its shared names were settled for them? The form left unsettled, if so. */
export function unsettledIn(p: Para, ids: string[]): string | null {
  const vague = p.vague;
  if (!vague || names(p, ids)) return null;
  const named = (id: string) => p.hits.some((h) => h.entityId === id);
  const vagueFor = (id: string) => vague.find((h) => h.shared?.ids.includes(id));
  if (!ids.every((id) => named(id) || vagueFor(id))) return null;
  const v = vagueFor(ids.find((id) => !named(id))!);
  return v ? (v.shared?.form ?? v.matched) : null;
}

/** "+ 4 paragraphs where "Isolde" isn't settled" */
export function unsettledLine(u: Unsettled | null): string {
  if (!u || !u.paragraphs) return "";
  return `+ ${u.paragraphs.toLocaleString()} ${u.paragraphs === 1 ? "paragraph" : "paragraphs"} where “${u.form}” isn’t settled`;
}

/**
 * The thread of `ids` (one entry, or two read together) through the chapters given in story order.
 * `mode` "paragraphs": the paragraphs that name them, with gaps between; "chapters": the chapters that name them, whole.
 */
export function thread(chapters: ThreadChapter[], matcher: Matcher, ids: string[], mode: "paragraphs" | "chapters"): {
  parts: ThreadPart[];
  paragraphs: number;
  chapters: number;
  unsettled: Unsettled | null;
} {
  const parts: ThreadPart[] = [];
  let total = 0;
  let unsettled = null as Unsettled | null;
  for (const chapter of chapters) {
    const paras = paragraphs(chapter.body, matcher);
    for (const p of paras) {
      const form = unsettledIn(p, ids);
      if (form) unsettled = { paragraphs: (unsettled?.paragraphs ?? 0) + 1, form: unsettled?.form ?? form };
    }
    const hits = paras.map((p) => names(p, ids));
    const count = hits.filter(Boolean).length;
    if (mode === "chapters") {
      // a chapter names both when each is named somewhere in it
      const all = paras.flatMap((p) => p.hits);
      if (!ids.every((id) => all.some((h) => h.entityId === id))) continue;
      total += count;
      parts.push({ chapter, blocks: paras.map((p, i) => ({ ...p, hit: hits[i]! })), count });
      continue;
    }
    if (!count) continue;
    total += count;
    const shown = new Set<number>();
    hits.forEach((h, i) => {
      if (!h) return;
      shown.add(i);
      if (paras[i - 1]?.margin) shown.add(i - 1);
      if (paras[i + 1]?.margin) shown.add(i + 1);
    });
    const order = [...shown].sort((a, b) => a - b);
    const blocks: (Para | Gap)[] = [];
    order.forEach((i, k) => {
      const prev = order[k - 1];
      if (prev !== undefined && i > prev + 1) blocks.push({ kind: "gap", paras: paras.slice(prev + 1, i) });
      blocks.push({ ...paras[i]!, hit: hits[i]! });
    });
    parts.push({ chapter, blocks, count });
  }
  return { parts, paragraphs: total, chapters: parts.length, unsettled };
}

/** A paragraph cut into plain text and names, for colouring. */
export function segments(p: Para): { text: string; hit?: Hit }[] {
  const out: { text: string; hit?: Hit }[] = [];
  let at = 0;
  for (const h of p.hits) {
    const s = h.start - p.from;
    const e = h.end - p.from;
    if (s < at) continue;
    if (s > at) out.push({ text: p.text.slice(at, s) });
    out.push({ text: p.text.slice(s, e), hit: h });
    at = e;
  }
  if (at < p.text.length) out.push({ text: p.text.slice(at) });
  return out;
}

/** "Varren: 212 paragraphs in 31 chapters", "Varren and Isolde: 18 paragraphs in 9 chapters" */
export function threadCount(names: string[], paragraphs: number, chapters: number): string {
  const p = `${paragraphs.toLocaleString()} ${paragraphs === 1 ? "paragraph" : "paragraphs"}`;
  const c = `${chapters.toLocaleString()} ${chapters === 1 ? "chapter" : "chapters"}`;
  return `${names.join(" and ")}: ${p} in ${c}`;
}
