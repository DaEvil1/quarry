// Reading one entry's thread (docs/SPEC.md §11.4): the paragraphs (or chapters) that name an entry, in story order,
// worked out in the browser from the chapters kept on the device and the same matcher that colours names, so it
// works on the phone without a network. With a second entry, only what names both.
//
// A paragraph is a line, as in the companion. A margin note (%% line) right before or after a shown paragraph comes
// with it, and a margin note that names the entry (both entries) is a hit of its own.

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

const MARGIN = /^[ \t]*%%/;

/** Every paragraph of a chapter with the names in it (likely misspellings aside). */
export function paragraphs(body: string, matcher: Matcher): Para[] {
  const out: Para[] = [];
  let from = 0;
  for (const line of body.split("\n")) {
    if (line.trim()) {
      const hits = matcher.scanLine(line, from, false).filter((h) => h.kind !== "near_miss");
      out.push({ kind: "para", from, text: line, hits, margin: MARGIN.test(line), hit: false });
    }
    from += line.length + 1;
  }
  return out;
}

const names = (p: Para, ids: string[]) => ids.every((id) => p.hits.some((h) => h.entityId === id));

/**
 * The thread of `ids` (one entry, or two read together) through the chapters given in story order.
 * `mode` "paragraphs": the paragraphs that name them, with gaps between; "chapters": the chapters that name them, whole.
 */
export function thread(chapters: ThreadChapter[], matcher: Matcher, ids: string[], mode: "paragraphs" | "chapters"): {
  parts: ThreadPart[];
  paragraphs: number;
  chapters: number;
} {
  const parts: ThreadPart[] = [];
  let total = 0;
  for (const chapter of chapters) {
    const paras = paragraphs(chapter.body, matcher);
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
  return { parts, paragraphs: total, chapters: parts.length };
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
