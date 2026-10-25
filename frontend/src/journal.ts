// Journal calls (docs/SPEC.md §14.1): entries are written in the chapter editor and saved like chapters, with
// revisions; the date and project are labels; what was planned in an entry is said before it is deleted.

import { ApiError, del, get, patch, post, put } from "./api";
import { DocConflict, type RevisionInfo } from "./manuscript";
import type { ItemOrigin, JournalDetail, JournalEntry } from "./types";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export const listJournal = (world: string, project = "") =>
  get<JournalEntry[]>(`${base(world)}/journal${project ? `?project=${encodeURIComponent(project)}` : ""}`);
export const getEntry = (world: string, id: string) => get<JournalDetail>(`${base(world)}/journal/${id}`);
/** A new entry; `id` is chosen here, so sending it twice (an offline phone retrying) makes one entry. */
export const createEntry = (world: string, entry: { id?: string; entry_date: string; title?: string | null; body?: string; project?: string | null }) =>
  post<JournalDetail>(`${base(world)}/journal`, entry);
export const deleteEntry = (world: string, id: string) => del(`${base(world)}/journal/${id}`);
export const entryTies = (world: string, id: string) =>
  get<{ facts: number; relationships: number; notes: number; items: number }>(`${base(world)}/journal/${id}/ties`);
/** The date and the project: labels, saved without the version check. */
export const setEntryAbout = (world: string, id: string, about: { entry_date?: string; project?: string | null }) =>
  patch<JournalEntry>(`${base(world)}/journal/${id}/about`, about);

/** The entry changed on another device since this one loaded it. */
export class EntryConflict extends DocConflict<JournalDetail> {
  constructor(current: JournalDetail) {
    super(current, "This entry changed on another device.");
  }
}

export async function saveEntry(
  world: string,
  id: string,
  baseVersion: number,
  changes: { title?: string; body?: string },
): Promise<JournalDetail> {
  try {
    const sent = changes.title === undefined ? changes : { ...changes, title: changes.title.trim() || null };
    return await patch<JournalDetail>(`${base(world)}/journal/${id}`, { base_version: baseVersion, ...sent });
  } catch (e) {
    const current = e instanceof ApiError && e.status === 409 ? (e.body as { entry?: JournalDetail } | null)?.entry : null;
    if (current) throw new EntryConflict(current);
    throw e;
  }
}

export const snapshotEntry = (world: string, id: string, reason: "autosnap" | "checkpoint" | "conflict" | "restore", extra: { label?: string; body?: string } = {}) =>
  post<{ id: string | null; skipped: boolean }>(`${base(world)}/journal/${id}/revisions`, { reason, ...extra });
export const listEntryRevisions = (world: string, id: string) => get<RevisionInfo[]>(`${base(world)}/journal/${id}/revisions`);
export const restoreEntry = (world: string, id: string, revisionId: string) =>
  post<JournalDetail>(`${base(world)}/journal/${id}/restore`, { revision_id: revisionId });

/** Open items linked to an entry, with the passage each was made from. */
export const entryItems = (world: string, id: string) =>
  get<{ id: string; kind: string; title: string | null; body: string; passage: string | null }[]>(`${base(world)}/journal/${id}/items`);

// ---- reading an entry's thread through the planning (docs/SPEC.md §14.2) ----

export interface PlanningItem {
  id: string;
  kind: string;
  status: string;
  title: string | null;
  body: string;
  closed_note: string | null;
  created_at: string;
  project: string | null;
  /** of the entries asked about: those it names, and those it is tagged with */
  names: string[];
  tagged: string[];
}

export interface PlanningDecision {
  id: string;
  decided_on: string;
  text: string;
  project: string | null;
  names: string[];
  tagged: string[];
}

export const planning = (world: string, entities: string[]) =>
  get<{ items: PlanningItem[]; decisions: PlanningDecision[] }>(
    `${base(world)}/planning?${entities.map((e) => `entity=${encodeURIComponent(e)}`).join("&")}`,
  );

// ---- the note for next time (docs/SPEC.md §14.4) and since this was written (§14.5) ----

export const entryNote = (world: string, id: string) =>
  get<{ note: string; cursor: number; updated_at: string | null }>(`${base(world)}/journal/${id}/session-note`);
export const saveEntryNote = (world: string, id: string, note: string, cursor: number) =>
  put<{ note: string; cursor: number }>(`${base(world)}/journal/${id}/session-note`, { note, cursor });

export interface SinceEntity {
  entity: { id: string; name: string; kind: string };
  decisions: { id: string; date: string; text: string }[];
  changes: { what: string; date: string }[];
  later: number;
}
export interface SinceThis {
  date: string;
  edited: string | null;
  decisions: number;
  changes: number;
  later: number;
  entities: SinceEntity[];
}
export const sinceThis = (world: string, id: string) => get<SinceThis>(`${base(world)}/journal/${id}/since`);

// ---- where an item came from ----

const day = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "long", year: "numeric" });
/** "2 March 2019", from an ISO date, read as that day wherever the device is. */
export const journalDay = (iso: string) => day.format(new Date(`${iso.slice(0, 10)}T12:00:00`));

/** "From chapter The Quay" / "From the Journal, 2 March 2019" */
export function originLine(o: ItemOrigin): string {
  return o.table === "journal" ? `From the Journal, ${o.date ? journalDay(o.date) : "an entry"}` : `From the chapter “${o.title ?? ""}”`;
}
