// Manuscript calls: chapters, their history, experiments, salvage, and export/restore of a world.

import { ApiError, del, get, patch, post, put } from "./api";
import type { EntityKind, Mention, World } from "./types";

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
  replaces_id: string | null;
  words: number;
  version: number;
  updated_at: string;
  retired_at: string | null;
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
  replaces_title: string | null;
  experiment_status: string | null;
}

export interface Manuscript {
  chapters: ChapterInfo[];
  experiments: ChapterInfo[];
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

/** The chapter changed on another device since this one loaded it; `current` is the server's copy. */
export class ChapterConflict extends Error {
  constructor(public current: Chapter) {
    super("This chapter changed on another device.");
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

/** A chapter's summary and status: labels, not text, so no version check. */
export const setAbout = (world: string, id: string, about: { summary?: string; status_id?: string | null }) =>
  patch<ChapterInfo>(`${base(world)}/chapters/${id}/about`, about);

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
