// The cuts bin (docs/SPEC.md §11.3): passages cut from a chapter with Ctrl+Shift+X, kept per project forever. A cut
// is kept on the device first and sent from the outbox, so cutting works offline; reading the bin needs the network.

import { del, get, post } from "./api";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

/** How much text either side of a cut is kept, to find its place again. */
export const CONTEXT = 80;

export interface Cut {
  id: string;
  project: string | null;
  body: string;
  before: string;
  after: string;
  words: number;
  cut_at: string;
  /** the source chapter, if it still exists */
  chapter: { id: string; title: string; state: string } | null;
  /** its title when it was cut */
  chapter_title: string;
  put_back_at: string | null;
  put_back_to: { id: string; title: string } | null;
  match: { before: string; match: string; after: string } | null;
}

export const listCuts = (world: string, project: string, q = "", putBack = false) => {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (putBack) params.set("put_back", "true");
  const qs = params.toString();
  return get<Cut[]>(`${base(world)}/projects/${encodeURIComponent(project)}/cuts${qs ? `?${qs}` : ""}`);
};
export const chapterCuts = (world: string, chapterId: string) => get<Cut[]>(`${base(world)}/chapters/${chapterId}/cuts`);
export const markPutBack = (world: string, cutId: string, chapterId: string) =>
  post<Cut>(`${base(world)}/cuts/${cutId}/put-back`, { chapter_id: chapterId });
export const removeCut = (world: string, cutId: string) => del(`${base(world)}/cuts/${cutId}`);

/** The text either side of a selection, kept with the cut. */
export function around(doc: string, from: number, to: number): { before: string; after: string } {
  return { before: doc.slice(Math.max(0, from - CONTEXT), from), after: doc.slice(to, to + CONTEXT) };
}

function occurrences(doc: string, text: string): number[] {
  const out: number[] = [];
  if (!text) return out;
  for (let i = doc.indexOf(text); i >= 0 && out.length < 2; i = doc.indexOf(text, i + 1)) out.push(i);
  return out;
}

/**
 * Where a cut was taken from, found by the text around it: the one place where what was before it is followed by
 * what was after it. If that is gone or found twice, the text on one side alone, if it is there exactly once (an
 * edit right at the other side shouldn't lose the place). Otherwise null: the cut goes in at the cursor instead.
 */
export function findPlace(doc: string, before: string, after: string): number | null {
  if (!before && !after) return doc.length === 0 ? 0 : null;
  const both = occurrences(doc, before + after);
  if (both.length === 1) return both[0] + before.length;
  if (both.length > 1) return null;
  if (before.length >= 12) {
    const b = occurrences(doc, before);
    if (b.length === 1) return b[0] + before.length;
  }
  if (after.length >= 12) {
    const a = occurrences(doc, after);
    if (a.length === 1) return a[0];
  }
  return null;
}

/** "Cut 84 words to the bin" */
export function cutLabel(words: number): string {
  return `Cut ${words.toLocaleString()} ${words === 1 ? "word" : "words"} to the bin`;
}
