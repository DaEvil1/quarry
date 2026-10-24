// Story time on the server: "is at" presence per chapter, and the Where-everyone-is grid.

import { del, get, put } from "./api";
import type { Presence, WhereGrid } from "./types";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export const chapterPresence = (world: string, chapterId: string) => get<Presence[]>(`${base(world)}/chapters/${chapterId}/presence`);
export const setPresence = (world: string, chapterId: string, entityId: string, placeId: string, note: string | null = null) =>
  put<Presence>(`${base(world)}/chapters/${chapterId}/presence/${entityId}`, { place_id: placeId, note });
export const clearPresence = (world: string, chapterId: string, entityId: string) =>
  del(`${base(world)}/chapters/${chapterId}/presence/${entityId}`);
/** The grid of entries across chapters: every entry of `kinds` named in the chapters shown (characters when not given),
 * plus `entities` picked by hand, limited to a project or not. */
export function whereGrid(world: string, opts: { project?: string; kinds?: string[]; entities?: string[] } = {}) {
  const q = new URLSearchParams();
  if (opts.project) q.set("project", opts.project);
  if (opts.kinds) q.set("kinds", opts.kinds.join(","));
  if (opts.entities?.length) q.set("entities", opts.entities.join(","));
  const qs = q.toString();
  return get<WhereGrid>(`${base(world)}/where${qs ? `?${qs}` : ""}`);
}
