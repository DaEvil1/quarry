// The writing companion's server side: the Checks, how findings were resolved, the note for next time, the items
// tied to a chapter, and which entries are already linked (so the companion doesn't ask again).

import { del, get, put } from "./api";
import type { EntityKind, EntityRef } from "./types";
import type { GraphData } from "./world/graph";
import { linkKey, type Finding } from "./world/findings";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export interface Check {
  rule: string;
  key: string;
  message: string;
  chapter: { id: string; title: string } | null;
  entities: EntityRef[];
  later: boolean;
  /** a conflicting fact's label and the entry's kind, for "Both are true (several values)" */
  label?: string;
  kind?: EntityKind;
  /** it rests on a planned fact or relationship (Include planned) */
  planned?: boolean;
  /** two holders of a one-at-a-time role: the earlier relationship, and the later one it can end before */
  end?: { id: string; name: string };
  before?: { id: string; name: string } | null;
}

export interface Resolution {
  id: string;
  rule: string;
  key: string;
  outcome: "intentional" | "later" | "not_connected";
  note: string | null;
}

/** The checks, for the world or one chapter; `planned`: planned facts and relationships count too (Include planned,
 * docs/SPEC.md §14.6). */
export const checks = (world: string, chapterId?: string, planned = false) => {
  const q = [chapterId ? `chapter=${encodeURIComponent(chapterId)}` : "", planned ? "planned=1" : ""].filter(Boolean).join("&");
  return get<Check[]>(`${base(world)}/checks${q ? `?${q}` : ""}`);
};
export const resolutions = (world: string) => get<Resolution[]>(`${base(world)}/resolutions`);
export const resolve = (world: string, rule: string, key: string, outcome: Resolution["outcome"], note: string | null = null) =>
  put<Resolution>(`${base(world)}/resolutions`, { rule, key, outcome, note });
export const unresolve = (world: string, id: string) => del(`${base(world)}/resolutions/${id}`);

export interface SessionNote {
  note: string;
  cursor: number;
  updated_at: string | null;
}
export const sessionNote = (world: string, chapterId: string) => get<SessionNote>(`${base(world)}/chapters/${chapterId}/session-note`);
export const saveSessionNote = (world: string, chapterId: string, note: string, cursor: number) =>
  put<SessionNote>(`${base(world)}/chapters/${chapterId}/session-note`, { note, cursor });

export const chapterItems = (world: string, chapterId: string) =>
  get<{ id: string; kind: string; title: string | null; body: string; passage: string | null }[]>(`${base(world)}/chapters/${chapterId}/items`);

/** Pairs of entries with any recorded relationship, either way round. */
export async function linkedPairs(world: string): Promise<Set<string>> {
  const g = await get<GraphData>(`${base(world)}/graph`);
  return new Set(g.edges.map((e) => linkKey(e.a, e.b)));
}

/** What the companion panel can do, provided by the chapter page. */
export interface PanelActions {
  jump(f: { from?: number; to?: number }): void;
  fix(f: Finding): void;
  /** never flag again (intentional), or keep on the Later list */
  resolve(rule: string, key: string, outcome: "intentional" | "later" | "not_connected"): void;
  link(a: EntityRef, b: EntityRef, typeId: string, forward: boolean): void;
  isAt(entity: EntityRef, place: EntityRef): void;
  create(word: string, kind: EntityKind): void;
  notAName(word: string): void;
  addSpelling(entity: EntityRef, word: string): void;
  summary(entity: EntityRef, text: string): void;
  open(entity: EntityRef): void;
  /** an entry of another book's bible named here: move it up to the world */
  share(entity: EntityRef): void;
  /** an expected label it hasn't got: open the fact on its page */
  addLabel(entity: EntityRef, label: string): void;
  /** a conflict that is two true values: the label holds several values for the kind */
  several(kind: EntityKind, label: string): void;
  /** two holders of a one-at-a-time role: end the earlier one where the later one starts */
  endBefore(earlier: string, later: string): void;
  /** evidence in a retired chapter: point it at another chapter */
  reAnchor(f: Finding, chapterId: string): void;
  saveNote(text: string): void;
  stash(): void;
  update(): void;
  goBack(): void;
  /** a TK or ?? line: make it a question, with the line as the passage (docs/SPEC.md §14.3.2) */
  question?(f: Finding): void;
  /** resting on an item made from a passage marks the passage in the text (null: unmark) */
  showPassage?(passage: string | null): void;
}
