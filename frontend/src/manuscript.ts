// Manuscript calls: chapters, their history, experiments, salvage, and export/restore of a world.

import { ApiError, del, get, patch, post, put } from "./api";
import type { EntityKind, EntityRef, Mention, TimeValue, World } from "./types";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export interface ChapterInfo {
  id: string;
  project: string;
  title: string;
  state: "current" | "experiment" | "retired";
  position: number;
  pov: { id: string; name: string } | null;
  /** one optional line about the chapter, and where it stands in the project's statuses */
  summary: string;
  status: StatusRef | null;
  experiment_item_id: string | null;
  words: number;
  version: number;
  updated_at: string;
  retired_at: string | null;
  /** when it is set and how it is told (docs/SPEC.md §13.1.2) */
  time_at?: number | null;
  time_end?: number | null;
  time_label?: string | null;
  time_approx?: boolean;
  outside_time?: boolean;
  told_as?: "flashback" | "tale" | null;
}

/** An open experiment (docs/SPEC.md §13.6.1): the current chapters it would replace (its range), or where it only
 * adds, and its drafts in order. */
export interface Experiment {
  id: string;
  title: string;
  status: string;
  range: { id: string; title: string; state: string; words: number }[];
  range_words: number;
  insert: { chapter_id: string; title: string; side: "before" | "after" } | null;
  drafts: ChapterInfo[];
  words: number;
  /** chapters of its range no longer in the book, and the experiment that replaced them */
  lost: string[];
  replaced_by: string | null;
}

export interface StatusRef {
  id: string;
  label: string;
  position: number;
}

export interface ChapterStatus extends StatusRef {
  /** chapters that have it (current, experiments and retired) */
  chapters: number;
}

export interface HarvestNote {
  id: string;
  body: string;
  created_at: string;
}

export interface Chapter extends ChapterInfo {
  body: string;
  mentions: Mention[];
  harvest_notes: HarvestNote[];
  /** for a draft: its experiment, with the range it would replace (or where it adds) and its drafts */
  experiment?: (Pick<Experiment, "id" | "title" | "status" | "range" | "insert" | "lost" | "replaced_by"> & { drafts: { id: string; title: string; position: number }[] }) | null;
  experiment_status: string | null;
}

export interface Manuscript {
  chapters: ChapterInfo[];
  experiments: Experiment[];
  pov_tally: { name: string; chapters: number }[];
  words: number;
  retired: number;
  /** the project's statuses in order (in a copy kept offline: only those its chapters have) */
  statuses?: StatusRef[];
  /** chapters and words per status, in order, then those with none (label null) */
  status_tally?: { id: string | null; label: string | null; chapters: number; words: number }[];
  /** per chapter: the characters and places named in it, most named first (missing in a copy kept offline) */
  cast?: Record<string, { id: string; name: string; kind: EntityKind; count: number }[]>;
}

export interface RevisionInfo {
  id: string;
  version: number;
  title: string;
  reason: "autosnap" | "checkpoint" | "state" | "restore" | "conflict" | "start";
  label: string | null;
  words: number;
  created_at: string;
}

export interface SalvageEntry extends ChapterInfo {
  harvest_notes: HarvestNote[];
  match: { before: string; match: string; after: string } | null;
  /** what its review did (docs/SPEC.md §13.6.2) */
  review?: { id: string; keep: number; move: number; planned: number; drop: number } | null;
  /** retired before reviews: what is still tied to it */
  still_tied?: { facts: number; relationships: number; is_at: number; items: number; notes: number } | null;
}

export const REASON_LABELS: Record<RevisionInfo["reason"], string> = {
  autosnap: "Saved automatically",
  checkpoint: "Checkpoint",
  state: "Before a change of state",
  restore: "Before a restore",
  conflict: "Conflict copy",
  start: "The text it started with",
};

const project = (world: string, p: string) => `${base(world)}/projects/${encodeURIComponent(p)}`;

export const getManuscript = (world: string, p: string) => get<Manuscript>(`${project(world, p)}/chapters`);
export const createChapter = (world: string, p: string, title: string) =>
  post<Chapter>(`${project(world, p)}/chapters`, { title });
export const reorderChapters = (world: string, p: string, ids: string[]) =>
  put<ChapterInfo[]>(`${project(world, p)}/chapter-order`, { ids });
export const getSalvage = (world: string, p: string, q = "") =>
  get<SalvageEntry[]>(`${project(world, p)}/salvage${q ? `?q=${encodeURIComponent(q)}` : ""}`);

export const getChapter = (world: string, id: string) => get<Chapter>(`${base(world)}/chapters/${id}`);
export const deleteChapter = (world: string, id: string) => del(`${base(world)}/chapters/${id}`);

/** A document (a chapter, a journal entry) changed on another device since this one loaded it; `current` is the
 * server's copy. */
export class DocConflict<T = unknown> extends Error {
  constructor(public current: T, message = "This changed on another device.") {
    super(message);
  }
}

/** The chapter changed on another device since this one loaded it; `current` is the server's copy. */
export class ChapterConflict extends DocConflict<Chapter> {
  constructor(current: Chapter) {
    super(current, "This chapter changed on another device.");
  }
}

export async function saveChapter(
  world: string,
  id: string,
  baseVersion: number,
  changes: { title?: string; body?: string; pov_entity_id?: string | null },
): Promise<Chapter> {
  try {
    return await patch<Chapter>(`${base(world)}/chapters/${id}`, { base_version: baseVersion, ...changes });
  } catch (e) {
    const current = e instanceof ApiError && e.status === 409 ? (e.body as { chapter?: Chapter } | null)?.chapter : null;
    if (current) throw new ChapterConflict(current);
    throw e;
  }
}

export const snapshot = (world: string, id: string, reason: "autosnap" | "checkpoint" | "conflict", extra: { label?: string; body?: string } = {}) =>
  post<{ id: string | null; skipped: boolean }>(`${base(world)}/chapters/${id}/revisions`, { reason, ...extra });
export const listRevisions = (world: string, id: string) => get<RevisionInfo[]>(`${base(world)}/chapters/${id}/revisions`);
export const getRevision = (world: string, id: string) =>
  get<RevisionInfo & { body: string }>(`${base(world)}/revisions/${id}`);
export const restoreRevision = (world: string, chapterId: string, revisionId: string) =>
  post<Chapter>(`${base(world)}/chapters/${chapterId}/restore`, { revision_id: revisionId });

export const retireChapter = (world: string, id: string, note: string) =>
  post<Chapter>(`${base(world)}/chapters/${id}/retire`, { note: note || null });
export const reinstateChapter = (world: string, id: string) => post<Chapter>(`${base(world)}/chapters/${id}/reinstate`);
export const addHarvestNote = (world: string, id: string, body: string) =>
  post<HarvestNote>(`${base(world)}/chapters/${id}/harvest-notes`, { body });

export const startExperiment = (world: string, id: string, start: "scratch" | "copy") =>
  post<Chapter>(`${base(world)}/chapters/${id}/experiments`, { start });
export const closeExperiment = (
  world: string,
  id: string,
  outcome: "accepted" | "rejected" | "harvested",
  opts: { note?: string; decision?: string; decided_on?: string },
) => post<Chapter>(`${base(world)}/chapters/${id}/close-experiment`, { outcome, ...opts });

// ---- revising and salvaging (docs/SPEC.md §11) ----

/** A chapter's summary, status, time and mark: labels, not text, so no version check. */
export type About = { summary?: string; status_id?: string | null; told_as?: "flashback" | "tale" | null } & Partial<TimeValue>;
export const setAbout = (world: string, id: string, about: About) => patch<ChapterInfo>(`${base(world)}/chapters/${id}/about`, about);

// ---- restructuring (docs/SPEC.md §13.6) ----

export const startRange = (
  world: string,
  p: string,
  body: { title: string; start: "scratch" | "copy"; range?: string[]; insert?: { chapter_id: string; side: "before" | "after" } },
) => post<Experiment & { first: string }>(`${project(world, p)}/experiments`, body);
export const getExperiment = (world: string, id: string) => get<Experiment>(`${base(world)}/experiments/${id}`);
export const addDraft = (world: string, id: string, body: { title?: string; copy_from?: string }) => post<Chapter>(`${base(world)}/experiments/${id}/drafts`, body);
export const orderDrafts = (world: string, id: string, ids: string[]) => put<Experiment>(`${base(world)}/experiments/${id}/drafts`, { ids });
export const setRange = (world: string, id: string, body: { range?: string[]; insert?: { chapter_id: string; side: "before" | "after" } }) =>
  put<Experiment>(`${base(world)}/experiments/${id}/range`, body);

/** One thing tied to chapters leaving the book, with the choices that apply. */
export interface Tie {
  key: string;
  kind: "fact" | "relationship" | "presence" | "link" | "note" | "event" | "telling";
  id: string;
  field: string;
  chapter: { id: string; title: string };
  text: string;
  evidence: string | null;
  entities: EntityRef[];
  choices: ("keep" | "move" | "planned" | "drop")[];
  default: "keep" | "move" | "planned" | "drop";
  keep_text: string | null;
  warn: string | null;
  move_to: { id: string; title: string } | null;
}
export interface Choice {
  key: string;
  action: Tie["default"];
  to?: string | null;
}
export interface Reviewed {
  id: string;
  summary: { keep: number; move: number; planned: number; drop: number };
  chapters: string[];
  said?: string[];
  first?: string | null;
  /** the decision an experiment's close logged (docs/SPEC.md §16.3) */
  decision_id?: string | null;
}
export const chapterTies = (world: string, ids: string[], experiment?: string) =>
  get<{ rows: Tie[] }>(`${base(world)}/chapters/ties?ids=${ids.join(",")}${experiment ? `&experiment=${experiment}` : ""}`);
export const retireMany = (world: string, ids: string[], review: Choice[], notes: Record<string, string>) =>
  post<Reviewed>(`${base(world)}/chapters/retire`, { ids, review, notes });
export const closeRange = (
  world: string,
  id: string,
  body: { outcome: "accepted" | "rejected" | "harvested"; review: Choice[]; notes: Record<string, string>; decision?: string; decided_on?: string },
) => post<Reviewed>(`${base(world)}/experiments/${id}/close`, body);
export const undoReview = (world: string, id: string) => post<{ restored: number; skipped: number }>(`${base(world)}/retire-reviews/${id}/undo`);
export const reviewRetired = (world: string, chapterId: string, review: Choice[]) => post<Reviewed>(`${base(world)}/chapters/${chapterId}/review`, { review });
export const reinstateRows = (world: string, chapterId: string) =>
  post<{ restored: number; skipped: number }>(`${base(world)}/chapters/${chapterId}/reinstate-review`);

/** The Archivist: evidence resting on a passage in a retired chapter (docs/SPEC.md §13.6.3). */
export interface EvidenceFinding {
  rule: "evidence_retired";
  key: string;
  kind: "fact" | "relationship" | "telling";
  id: string;
  message: string;
  chapter: { id: string; title: string };
  passage: string;
  entities: EntityRef[];
  /** chapters where the passage is found now (current ones and drafts) */
  found: { id: string; title: string; state: string }[];
}
export const evidenceRetired = (world: string) => get<EvidenceFinding[]>(`${base(world)}/evidence-retired`);
export const reAnchor = (world: string, kind: EvidenceFinding["kind"], id: string, chapterId: string) =>
  post(`${base(world)}/evidence/re-anchor`, { kind, id, chapter_id: chapterId });

/** "14 kept, 3 moved, 1 dropped". */
export function reviewLine(s: { keep: number; move: number; planned: number; drop: number }): string {
  const parts = [[s.keep, "kept"], [s.move, "moved"], [s.planned, "marked planned"], [s.drop, "dropped"]] as const;
  return parts.filter(([n]) => n).map(([n, w]) => `${n} ${w}`).join(", ") || "nothing tied";
}

export const statuses = {
  list: (world: string, p: string) => get<ChapterStatus[]>(`${project(world, p)}/statuses`),
  add: (world: string, p: string, label: string) => post<ChapterStatus[]>(`${project(world, p)}/statuses`, { label }),
  rename: (world: string, id: string, label: string) => patch<ChapterStatus[]>(`${base(world)}/statuses/${id}`, { label }),
  remove: (world: string, id: string) => del<ChapterStatus[]>(`${base(world)}/statuses/${id}`),
  order: (world: string, p: string, ids: string[]) => put<ChapterStatus[]>(`${project(world, p)}/status-order`, { ids }),
};

/** How strongly a status pill is drawn: the first status faint, the last the strongest (0.25 … 1). */
export function statusStrength(position: number, count: number): number {
  return count <= 1 ? 1 : 0.25 + (0.75 * Math.min(position, count - 1)) / (count - 1);
}

export const checkpointAll = (world: string, p: string, label: string) =>
  post<{ chapters: number; label: string }>(`${project(world, p)}/checkpoint`, { label });

export interface WordHistory {
  revisions: { at: string; chapter_id: string; added: number; removed: number }[];
  /** the working text against each chapter's last revision: counts for today */
  pending: { chapter_id: string; added: number; removed: number }[];
  chapters: Record<string, string>;
}
export const getWordHistory = (world: string, p: string) => get<WordHistory>(`${project(world, p)}/word-history`);

export interface FindOptions {
  find: string;
  match_case: boolean;
  whole_words: boolean;
  scope: "project" | "world";
}
export interface FoundChapter {
  id: string;
  title: string;
  state: "current" | "experiment";
  project: string;
  project_name: string;
  version: number;
  hits: { start: number; end: number; before: string; match: string; after: string }[];
}
export interface Replaced {
  replaced: number;
  label: string;
  chapters: { id: string; title: string; replaced: number; version: number; revision_id: string }[];
  skipped: { id: string; title: string; reason: string }[];
}
export const findInChapters = (world: string, p: string, opts: FindOptions) =>
  post<{ chapters: FoundChapter[]; total: number }>(`${project(world, p)}/find`, opts);
export const replaceInChapters = (
  world: string,
  p: string,
  opts: FindOptions & { replace: string; chapters: { id: string; version: number; hits: number[] }[] },
) => post<Replaced>(`${project(world, p)}/replace`, opts);
export const undoReplace = (world: string, p: string, done: Replaced) =>
  post<{ restored: { id: string; title: string }[]; skipped: { id: string; title: string; reason: string }[] }>(
    `${project(world, p)}/replace/undo`,
    { chapters: done.chapters.map((c) => ({ id: c.id, revision_id: c.revision_id, version: c.version })) },
  );

export const exportUrl = (world: string) => `${base(world)}/export`;

/** Upload an export zip; Quarry makes a new world from it. */
export async function restoreWorld(file: File): Promise<World> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/worlds/restore", { method: "POST", body: form, credentials: "same-origin" });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    throw new ApiError(res.status, typeof detail === "string" ? detail : `Restore failed (${res.status}).`, data);
  }
  return data as World;
}
