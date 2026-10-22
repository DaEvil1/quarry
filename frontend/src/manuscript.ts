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
  experiment_item_id: string | null;
  replaces_id: string | null;
  words: number;
  version: number;
  updated_at: string;
  retired_at: string | null;
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
  /** per chapter: the characters and places named in it, most named first (missing in a copy kept offline) */
  cast?: Record<string, { id: string; name: string; kind: EntityKind; count: number }[]>;
}

export interface RevisionInfo {
  id: string;
  version: number;
  title: string;
  reason: "autosnap" | "checkpoint" | "state" | "restore" | "conflict";
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
